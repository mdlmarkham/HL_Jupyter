#!/usr/bin/env python3
"""
Papermill Gateway - Flask API for executing Jupyter notebooks via Papermill
"""
from flask import Flask, request, send_file, jsonify
import papermill as pm
import nbformat
import tempfile
import os
import traceback

app = Flask(__name__)

@app.route('/')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'papermill-gateway'})

@app.post('/run')
def run_notebook():
    try:
        payload = request.get_json(force=True)
        nb_json = payload.get("notebook", payload)      # ← NEW

        with tempfile.NamedTemporaryFile(suffix='.ipynb', delete=False) as src, \
             tempfile.NamedTemporaryFile(suffix='.ipynb', delete=False) as dst:

            nbformat.write(nb_json, src)                # now has .cells
            src.flush()

            pm.execute_notebook(
                src.name,
                dst.name,
                kernel_name=nb_json.get("metadata", {})
                                   .get("kernelspec", {})
                                   .get("name", "python3"),
                progress_bar=False
            )

            return send_file(
                dst.name,
                mimetype='application/x-ipynb+json',
                download_name=os.path.basename(dst.name)
            )

    except Exception as e:
        return jsonify({"error": str(e),
                        "trace": traceback.format_exc()}), 500


if __name__ == '__main__':
    port = int(os.environ.get('GATEWAY_PORT', 5005))
    app.run(host='0.0.0.0', port=port)
