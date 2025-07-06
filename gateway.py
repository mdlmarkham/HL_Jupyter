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
RESULT_TAG = "results"  # keep lowercase, papermill lower-cases tags
USE_SCRAPBOOK = True    # glue is safer for data frames

def _extract_results(nb_path: str) -> dict:
    """Return a clean JSON-serialisable dict of glued scraps OR fallback tag scan."""
    if USE_SCRAPBOOK:
        import scrapbook as sb
        book = sb.read_notebook(nb_path)  # ⇢ Scrapbook.Notebook
        return {k: _jsonify(v.data) for k, v in book.scraps.items()}
    else:
        out = {}
        nb = nbformat.read(nb_path, as_version=4)
        for c in nb.cells:
            # Check both locations for tags
            tags = c.metadata.get("tags", [])
            papermill_tags = c.metadata.get("papermill", {}).get("tags", [])
            all_tags = tags + papermill_tags
            
            if RESULT_TAG in all_tags:
                for o in c.get("outputs", []):
                    if "data" in o:  # execute_result / display_data
                        key = f"cell_{c.execution_count}"
                        out[key] = _jsonify(o["data"])
        return out

def _jsonify(payload):
    """Make pandas/NumPy types JSON friendly."""
    import pandas as pd
    import numpy as np
    import json
    
    if isinstance(payload, pd.DataFrame):
        return json.loads(payload.to_json(orient="split"))
    if isinstance(payload, (pd.Series, np.generic)):
        return payload.tolist()
    if isinstance(payload, dict):
        return {k: _jsonify(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_jsonify(item) for item in payload]
    # Handle numpy arrays
    if hasattr(payload, 'tolist'):
        return payload.tolist()
    return payload

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
                    "error_type": "papermill_execution_error",
                    "cell": ex.exec_count,
                    "ename": ex.ename,
                    "evalue": ex.evalue,
                    "cell_source": cell_src,
                    "traceback": ex.traceback.splitlines()[-15:] if ex.traceback else []
                }
                return jsonify(err_payload), http.HTTPStatus.UNPROCESSABLE_ENTITY
            except ModuleNotFoundError as ex:  # catches missing libs
                return jsonify({
                    "error_type": "module_not_found",
                    "module": getattr(ex, 'name', 'unknown'),
                    "message": str(ex)
                }), http.HTTPStatus.BAD_REQUEST
            except Exception as ex:
                return jsonify({
                    "error_type": "kernel_startup", 
                    "message": str(ex)
                }), 500

            # ---------- 3. Extract results from executed notebook ----------
            try:
                results = _extract_results(str(dst_path))
                return jsonify({"results": results})
            except Exception as ex:
                return jsonify({
                    "error_type": "result_extraction_error",
                    "message": str(ex)
                }), 500

    except Exception as exc:
        return jsonify({
            "error": str(exc),
            "trace": traceback.format_exc().splitlines()[-10:]
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('GATEWAY_PORT', 5005))
    app.run(host='0.0.0.0', port=port)
