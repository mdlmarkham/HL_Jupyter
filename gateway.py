#!/usr/bin/env python3
"""
Papermill Gateway - Flask API for executing Jupyter notebooks via Papermill
"""
from flask import Flask, request, send_file, jsonify
import papermill as pm
import nbformat
import tempfile, os, traceback

app = Flask(__name__)

@app.route('/')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'papermill-gateway'})

@app.post("/run")
def run_notebook():
    try:
        payload = request.get_json(force=True)

        # --- unwrap n8n list / dict wrappers ----------------------------
        if isinstance(payload, list):
            if not payload:
                return jsonify({"error": "Empty JSON array"}), 400
            payload = payload[0]
        nb_json = payload.get("notebook", payload)

        # --- validate + convert to NotebookNode -------------------------
        if "cells" not in nb_json:
            return jsonify({"error": "Invalid notebook JSON – missing 'cells'"}), 400
        nb_node = nbformat.from_dict(nb_json)        # ← *** KEY LINE ***

        # --- write, execute, return ------------------------------------
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         suffix=".ipynb", delete=False) as src, \
             tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         suffix=".ipynb", delete=False) as dst:

            nbformat.write(nb_node, src)
            src.flush()

            pm.execute_notebook(
                src.name,
                dst.name,
                kernel_name=nb_node.metadata.kernelspec.name,
                progress_bar=False
            )

            return send_file(dst.name,
                             mimetype="application/x-ipynb+json",
                             download_name=os.path.basename(dst.name))

    except Exception as exc:
        return jsonify({"error": str(exc), "trace": traceback.format_exc()}), 500


if __name__ == '__main__':
    port = int(os.environ.get('GATEWAY_PORT', 5005))
    app.run(host='0.0.0.0', port=port)
