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
import time

app = Flask(__name__)
start_time = time.time()  # Track service start time

# Configuration
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # Global 5MB limit
MAX_NOTEBOOK_SIZE_MB = 5
ALLOWED_KERNELS = {"python3", "python"}  # whitelist
RESULT_TAG = "results"  # keep lowercase, papermill lower-cases tags
USE_SCRAPBOOK = True    # glue is safer for data frames
EXECUTION_TIMEOUT = 300  # 5 minutes max execution time

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
        return json.loads(payload.to_json(orient="split", date_format="iso"))
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

def _check_missing_imports(nb_node) -> list:
    """Pre-scan notebook for missing imports to fail fast."""
    import re
    import pkg_resources
    
    installed_packages = {pkg.project_name.lower() for pkg in pkg_resources.working_set}
    missing = []
    
    for cell in nb_node.cells:
        if cell.cell_type == 'code':
            # Simple regex to find import statements
            imports = re.findall(r'^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)', cell.source, re.MULTILINE)
            for imp in imports:
                # Check common package name mappings
                package_map = {
                    'cv2': 'opencv-python',
                    'PIL': 'pillow',
                    'sklearn': 'scikit-learn'
                }
                check_name = package_map.get(imp, imp)
                if check_name.lower() not in installed_packages:
                    missing.append(imp)
    
    return list(set(missing))  # deduplicate

@app.route('/')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'papermill-gateway'})

@app.route('/metrics')
def metrics():
    """Basic metrics endpoint for monitoring"""
    import psutil
    import time
    
    return jsonify({
        'service': 'papermill-gateway',
        'uptime': time.time() - start_time,
        'memory_usage_mb': psutil.Process().memory_info().rss / 1024 / 1024,
        'cpu_percent': psutil.cpu_percent(interval=0.1),
        'config': {
            'max_notebook_size_mb': MAX_NOTEBOOK_SIZE_MB,
            'execution_timeout': EXECUTION_TIMEOUT,
            'use_scrapbook': USE_SCRAPBOOK,
            'allowed_kernels': list(ALLOWED_KERNELS)
        }
    })

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
        language = (nb_node.metadata
                          .get("language_info", {})
                          .get("name", "python"))
        
        if kernelspec not in ALLOWED_KERNELS:
            return jsonify({"error": f"Kernel '{kernelspec}' not allowed"}), 400
        if language not in {"python"}:
            return jsonify({"error": f"Language '{language}' not supported"}), 400

        # ---------- 1.5. Pre-check for missing imports ----------
        try:
            missing_imports = _check_missing_imports(nb_node)
            if missing_imports:
                return jsonify({
                    "error_type": "missing_dependencies",
                    "missing_modules": missing_imports,
                    "message": f"Missing required modules: {', '.join(missing_imports)}"
                }), 422
        except Exception:
            # If import checking fails, continue anyway (don't block execution)
            pass

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
                    log_output=False,
                    start_timeout=60,  # Don't wait forever for kernel start
                    execution_timeout=EXECUTION_TIMEOUT  # Max execution time
                )
            except pm.exceptions.PapermillExecutionError as ex:
                # Extract cell source for better error context
                cell_src = ""
                if ex.exec_count and ex.exec_count <= len(nb_node.cells):
                    cell_src = nb_node.cells[ex.exec_count-1].source
                
                # Handle traceback - can be string or list
                tb = ex.traceback or []
                if isinstance(tb, str):
                    tb = tb.splitlines()
                
                err_payload = {
                    "error_type": "papermill_execution_error",
                    "cell": ex.exec_count,
                    "ename": ex.ename,
                    "evalue": ex.evalue,
                    "cell_source": cell_src,
                    "traceback": tb[-15:],  # Last 15 lines, whichever form it was
                    "output_nb": str(dst_path) if dst_path.exists() else None  # Path to executed notebook
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
                return jsonify({"results": results}), 200  # Explicit 200 OK
            except Exception as ex:
                return jsonify({
                    "error_type": "result_extraction_error",
                    "message": str(ex),
                    "output_nb": str(dst_path) if dst_path.exists() else None
                }), 500

    except Exception as exc:
        return jsonify({
            "error_type": "gateway_error",
            "error": str(exc),
            "trace": traceback.format_exc().splitlines()[-10:]
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('GATEWAY_PORT', 5005))
    app.run(host='0.0.0.0', port=port)
