#!/usr/bin/env python3
"""
Papermill Gateway - Flask API for executing Jupyter notebooks via Papermill
"""
from flask import Flask, request, send_file, jsonify
import papermill as pm
import nbformat
import tempfile, os, traceback
import json
from pathlib import Path
import http

app = Flask(__name__)

# Configuration
MAX_NOTEBOOK_SIZE_MB = 5
ALLOWED_KERNELS = {"python3", "python"}  # whitelist

@app.route('/')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'papermill-gateway'})

@app.post("/run")
def run_notebook():
    try:
        # ---------- 0. Size guard ----------
        if request.content_length and request.content_length > MAX_NOTEBOOK_SIZE_MB * 1024 * 1024:
            return jsonify({"error": "Notebook too large"}), 413

        # ---------- 1. Unwrap + validate ----------
        payload = request.get_json(force=True) or {}
        
        # unwrap n8n list / dict wrappers
        if isinstance(payload, list):
            if not payload:
                return jsonify({"error": "Empty JSON array"}), 400
            payload = payload[0]
        nb_json = payload.get("notebook", payload)

        # validate + convert to NotebookNode
        if "cells" not in nb_json:
            return jsonify({"error": "Invalid notebook JSON – missing 'cells'"}), 400
            
        try:
            nb_node = nbformat.from_dict(nb_json)
        except Exception as e:
            return jsonify({"error": f"Notebook JSON invalid: {e}"}), 400

        # kernel validation
        kernelspec = (nb_node.metadata
                            .get("kernelspec", {})
                            .get("name", "python3"))
        if kernelspec not in ALLOWED_KERNELS:
            return jsonify({"error": f"Kernel '{kernelspec}' not allowed"}), 400

        # ---------- 2. Execute in temporary directory ----------
        with tempfile.TemporaryDirectory() as tdir:
            src_path = Path(tdir) / "input.ipynb"
            dst_path = Path(tdir) / "output.ipynb"
            
            # write notebook to temp file
            with src_path.open("w", encoding="utf-8") as f:
                nbformat.write(nb_node, f)

            try:
                pm.execute_notebook(
                    str(src_path),
                    str(dst_path),
                    kernel_name=kernelspec,
                    progress_bar=False,
                    log_output=False
                )
            except pm.exceptions.PapermillExecutionError as ex:
                # Extract cell source for better error context
                cell_src = ""
                if ex.exec_count and ex.exec_count <= len(nb_node.cells):
                    cell_src = nb_node.cells[ex.exec_count-1].source
                
                err_payload = {
                    "error_type": "execution",
                    "ename": ex.ename,
                    "evalue": ex.evalue,
                    "cell_index": ex.exec_count,
                    "cell_source": cell_src,
                    "traceback": ex.traceback.splitlines()[-8:] if ex.traceback else []
                }
                return jsonify(err_payload), http.HTTPStatus.UNPROCESSABLE_ENTITY
            except Exception as ex:
                return jsonify({
                    "error_type": "kernel_startup", 
                    "message": str(ex)
                }), 500

            # ---------- 3. Extract results from executed notebook ----------
            RESULT_TAG = "result"
            
            results = []
            nb_executed = nbformat.read(str(dst_path), as_version=4)
            
            for cell in nb_executed.cells:
                if RESULT_TAG in cell.metadata.get("tags", []):
                    for output in cell.get("outputs", []):
                        txt = None
                        if output.output_type == "stream":
                            txt = output.get("text", "")
                        elif output.output_type == "execute_result":
                            txt = output.get("data", {}).get("text/plain", "")
                        
                        if txt:
                            try:
                                txt = json.loads(txt)   # JSON? great – use native
                            except Exception:
                                pass                   # leave as raw string
                            results.append(txt)

            return jsonify({"results": results})

    except Exception as exc:
        return jsonify({
            "error": str(exc),
            "trace": traceback.format_exc().splitlines()[-10:]
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('GATEWAY_PORT', 5005))
    app.run(host='0.0.0.0', port=port)
