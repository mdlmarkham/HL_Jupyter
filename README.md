# Homelab Jupyter & Papermill Gateway

A production-ready Docker Compose stack for running Jupyter notebooks interactively and programmatically via REST API. Optimized for homelab environments with advanced error handling, result extraction, and operational monitoring.

## Architecture

The stack consists of three complementary services sharing dependencies and storage:

- **🔬 Jupyter Lab**: Interactive development environment for creating and testing notebooks
- **⚡ Papermill Gateway**: Production REST API for automated notebook execution via Papermill
- **🤖 Jupyter MCP Server**: Model Context Protocol server for AI agent integration with Jupyter notebooks

Both services share the same Python environment through a common `requirements.txt` file, ensuring consistency and eliminating dependency conflicts.

## Features

### Jupyter Lab Service

- 🚀 JupyterLab enabled with nbconvert server extensions
- 🔒 Homelab-optimized (authentication disabled for internal use)
- 📊 Resource management with memory (4GB) and CPU (2 cores) limits
- 🔄 Automatic container restart with health monitoring
- 📁 Dual storage: persistent volume + local directory mapping
- 🐍 Full data science stack (pandas, numpy, matplotlib, scikit-learn, etc.)

### Papermill Gateway Service  

- 🌐 Production REST API for notebook execution (`POST /run`)
- 📈 Operational metrics endpoint (`GET /metrics`) with system monitoring
- 🛡️ Multi-layer security: size limits, kernel whitelist, timeout enforcement
- ⚠️ Rich error handling with cell-level context and structured responses
- 📦 Scrapbook integration for robust DataFrame and complex data extraction
- ⏱️ Configurable execution (300s) and kernel start (60s) timeouts
- 🔍 Pre-flight dependency checking to fail fast on missing modules
- 🗂️ Support for both n8n payload formats and raw notebook JSON

### Jupyter MCP Server

- 🤖 Model Context Protocol (MCP) server for AI agent integration
- ⚡ Real-time control and monitoring of Jupyter notebooks
- 🔁 Smart execution with automatic cell failure handling
- 🤝 Compatible with Claude Desktop, Cursor, Windsurf, and other MCP clients
- 🔧 Advanced tools for notebook manipulation: `insert_execute_code_cell`, `append_markdown_cell`, `get_notebook_info`, `read_cell`
- 🌐 Accessible on port 4040 for MCP client connections
- 📊 Integration with shared Jupyter workspace for seamless notebook access

## Prerequisites

- Docker Engine 20.10.0+
- Docker Compose V2
- 8GB+ available RAM (4GB Jupyter + 2GB Gateway + 2GB system overhead)
- 3+ CPU cores recommended
- 5GB+ disk space for container images and dependencies

## Quick Start

1. Clone this repository:

```bash
git clone <your-repo-url>
cd <repo-directory>
```

1. Create the notebooks directory:

```bash
mkdir notebooks
```

1. Start both services:

```bash
docker compose up -d
```

1. Access the services:

   - **Jupyter Lab**: <http://localhost:8888> (interactive development)
   - **Papermill Gateway**: <http://localhost:5005> (API endpoint)
   - **Gateway Metrics**: <http://localhost:5005/metrics> (monitoring)
   - **Jupyter MCP Server**: <http://localhost:4040> (MCP protocol endpoint for AI agents)

## API Usage

### Execute a Notebook

Send a POST request to the gateway with notebook JSON. The gateway supports both raw notebook JSON and n8n-wrapped payloads:

```bash
curl -X POST http://localhost:5005/run \
  -H "Content-Type: application/json" \
  -d '{
    "notebook": {
      "cells": [
        {
          "cell_type": "code",
          "source": "import pandas as pd\nresult = {\"message\": \"Hello World\"}\nprint(result)",
          "metadata": {"tags": ["results"]}
        }
      ],
      "metadata": {
        "kernelspec": {"name": "python3", "display_name": "Python 3"}
      }
    }
  }'
```

### Using Scrapbook for Results (Recommended)

For robust data extraction, especially with DataFrames and complex types, use Scrapbook in your notebook cells:

```python
import scrapbook as sb
import pandas as pd

# Your analysis code
df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [95, 87]})
summary_stats = {"mean_score": df.score.mean(), "total_records": len(df)}

# Capture results with Scrapbook (preferred method)
sb.glue("analysis_results", df)
sb.glue("summary", summary_stats)
```

The gateway will return structured JSON with automatic DataFrame serialization:

```json
{
  "results": {
    "analysis_results": {
      "columns": ["name", "score"],
      "index": [0, 1], 
      "data": [["Alice", 95], ["Bob", 87]]
    },
    "summary": {
      "mean_score": 91.0,
      "total_records": 2
    }
  }
}
```

### Error Handling

The gateway provides detailed error information for different failure scenarios:

#### Execution Errors

```json
{
  "error_type": "papermill_execution_error",
  "cell": 2,
  "ename": "NameError",
  "evalue": "name 'undefined_variable' is not defined",
  "cell_source": "print(undefined_variable)",
  "traceback": ["Traceback (most recent call last):", "  File...", "NameError: name 'undefined_variable' is not defined"],
  "output_nb": "/tmp/tmpxyz/output.ipynb"
}
```

#### Missing Dependencies

```json
{
  "error_type": "missing_dependencies", 
  "missing_modules": ["tensorflow", "opencv"],
  "message": "Missing required modules: tensorflow, opencv"
}
```

#### Kernel Issues

```json
{
  "error_type": "kernel_startup",
  "message": "Kernel failed to start within timeout period"
}
```

### Alternative: Tag-based Results

If you prefer not to use Scrapbook, you can still extract results using cell tags:

```python
# In a notebook cell, add "results" tag via metadata
result_data = {"status": "completed", "value": 42}
result_data  # This will be captured if cell has "results" tag
```

## Configuration

### Environment Variables

### Environment Variables

#### Jupyter Service

- `JUPYTER_TOKEN`: Authentication token for accessing Jupyter (default: "changeme")
- `JUPYTER_ENABLE_LAB`: Enables JupyterLab interface (default: "yes")
- `NB_UID`: User ID for the Jupyter user (default: 1000)
- `NB_GID`: Group ID for the Jupyter user (default: 100)

#### Gateway Service

- `GATEWAY_PORT`: Port for the gateway service (default: 5005)
- `MAX_NOTEBOOK_SIZE_MB`: Maximum notebook size in MB (default: 5)
- `EXECUTION_TIMEOUT`: Maximum execution time in seconds (default: 300)
- `USE_SCRAPBOOK`: Enable Scrapbook for result extraction (default: true)

#### MCP Server Service

- `ROOM_URL`: URL to the Jupyter service (default: "http://jupyter:8888")
- `ROOM_TOKEN`: Authentication token for Jupyter access (uses JUPYTER_TOKEN)
- `ROOM_ID`: Default notebook file to work with (default: "notebook.ipynb")
- `RUNTIME_URL`: Runtime URL for Jupyter kernels (default: same as ROOM_URL)
- `RUNTIME_TOKEN`: Runtime authentication token (uses JUPYTER_TOKEN)

### Gateway Configuration

The gateway includes several built-in security and performance controls:

```python
# Security Controls
MAX_CONTENT_LENGTH = 5MB        # Global request size limit
ALLOWED_KERNELS = ["python3", "python"]  # Kernel whitelist
ALLOWED_LANGUAGES = ["python"]  # Language whitelist

# Performance Controls  
EXECUTION_TIMEOUT = 300         # Max notebook execution time (5 minutes)
KERNEL_START_TIMEOUT = 60       # Max kernel startup time (1 minute)

# Result Extraction
USE_SCRAPBOOK = True           # Use Scrapbook for robust data extraction
RESULT_TAG = "results"         # Fallback tag for non-Scrapbook results
```

### Shared Dependencies

Both services install the same Python packages from `requirements.txt`:

- **Core**: papermill, flask, jupyter ecosystem
- **Data Science**: pandas, numpy, matplotlib, seaborn, plotly, scikit-learn  
- **Result Extraction**: scrapbook (for robust DataFrame serialization)
- **Monitoring**: psutil (for metrics endpoint)
- **Utilities**: requests, pyyaml

### Resource Limits

The containers are configured with the following resource constraints:

#### Jupyter Resources

- Memory: 4GB maximum
- CPU: 2 cores maximum
- Health check: Every 30s with 60s startup grace period

#### Gateway Resources  

- Memory: 2GB maximum
- CPU: 1 core maximum
- Health check: Every 30s with 60s startup grace period

#### MCP Server Resources

- Memory: 1GB maximum
- CPU: 0.5 core maximum
- Health check: Every 30s with 30s startup grace period
- Port: 4040 for MCP protocol communication

## MCP Client Configuration

The Jupyter MCP Server enables AI agents to interact directly with your Jupyter environment. Here's how to configure popular MCP clients:

### Claude Desktop (Windows/macOS)

Add this configuration to your Claude Desktop settings (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "ROOM_URL=http://host.docker.internal:8888",
        "-e", "ROOM_TOKEN=changeme",
        "-e", "ROOM_ID=notebook.ipynb",
        "-e", "RUNTIME_URL=http://host.docker.internal:8888", 
        "-e", "RUNTIME_TOKEN=changeme",
        "datalayer/jupyter-mcp-server:latest"
      ]
    }
  }
}
```

### Linux MCP Client Configuration

For Linux systems, use `localhost` instead of `host.docker.internal`:

```json
{
  "mcpServers": {
    "jupyter": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm", "--network=host",
        "-e", "ROOM_URL=http://localhost:8888",
        "-e", "ROOM_TOKEN=changeme",
        "-e", "ROOM_ID=notebook.ipynb",
        "-e", "RUNTIME_URL=http://localhost:8888",
        "-e", "RUNTIME_TOKEN=changeme",
        "datalayer/jupyter-mcp-server:latest"
      ]
    }
  }
}
```

### Available MCP Tools

The Jupyter MCP Server provides these tools for AI agents:

- `insert_execute_code_cell`: Insert and execute code in notebooks
- `append_markdown_cell`: Add markdown documentation
- `get_notebook_info`: Retrieve notebook structure and metadata
- `read_cell`: Read specific notebook cells
- `list_notebooks`: List available notebooks in the workspace

### Testing MCP Connection

Verify the MCP server is running and accessible:

```bash
# Test basic connectivity
curl -f http://localhost:4040/health

# Test MCP protocol (if using HTTP transport)
curl -X POST http://localhost:4040 \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/list", "params": {}}'
```

For complete MCP tools documentation, visit: <https://jupyter-mcp-server.datalayer.tech/tools>

### Persistent Storage

The stack uses a dual storage approach optimized for both persistence and accessibility:

#### Shared Volume: `jupyter-data`

- Location: `/home/jovyan/work` (both services)
- Purpose: Execution workspace and temporary files
- Persistence: Managed by Docker, survives container restarts
- Access: Container-only

#### Local Directory: `./notebooks`

- Location: `/home/jovyan/notebooks` (both services)
- Purpose: Source notebooks and development files
- Persistence: Direct host filesystem mapping
- Access: Available from host for version control and backup

### Networking

- **Jupyter**: Port 8888 (host) → 8888 (container)
- **Gateway**: Port 5005 (host) → 5005 (container)  
- **MCP Server**: Port 4040 (host) → 4040 (container)
- **Metrics**: Available at gateway port `/metrics` endpoint
- Network: Isolated `default` bridge network
- Internal communication: Services can communicate via service names

### Health Monitoring

All services include comprehensive health monitoring:

#### Service Health

- **Jupyter**: HTTP check on `/api` endpoint every 30s
- **Gateway**: HTTP check on `/` endpoint every 30s  
- **MCP Server**: HTTP check on `/health` endpoint every 30s
- **Timeout**: 10s with 3 retries before marking unhealthy
- **Startup Grace**: 60s for Jupyter/Gateway, 30s for MCP Server

#### Operational Metrics

The gateway provides a `/metrics` endpoint with real-time system information:

```bash
curl http://localhost:5005/metrics
```

Returns:

```json
{
  "service": "papermill-gateway",
  "uptime": 3600.5,
  "memory_usage_mb": 145.2,
  "cpu_percent": 2.1,
  "config": {
    "max_notebook_size_mb": 5,
    "execution_timeout": 300,
    "use_scrapbook": true,
    "allowed_kernels": ["python3", "python"]
  }
}
```

## Maintenance

### Updating

To update to the latest images and dependencies:

```bash
docker compose pull
docker compose down
docker compose up -d
```

### Logs

View logs for specific services:

```bash
# Gateway logs
docker compose logs -f papermill-gateway

# Jupyter logs  
docker compose logs -f jupyter

# All services
docker compose logs -f
```

### Backup

#### Notebooks Directory

The `./notebooks` directory can be backed up directly:

```bash
tar -czf notebooks-backup-$(date +%Y%m%d).tar.gz notebooks/
```

#### Jupyter Data Volume

For the Docker-managed volume:

```bash
docker run --rm \
  -v jupyter-data:/source \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/jupyter-data-$(date +%Y%m%d).tar.gz -C /source .
```

### Performance Tuning

#### Resource Adjustment

Modify `compose.yaml` resource limits based on your workload:

```yaml
services:
  jupyter:
    mem_limit: 8g      # Increase for large datasets
    cpus: "4"          # More cores for parallel processing
    
  papermill-gateway:
    mem_limit: 4g      # Increase for memory-intensive notebooks
    cpus: "2"          # More cores for concurrent requests
```

#### Timeout Configuration

Adjust timeouts for long-running notebooks:

```yaml
environment:
  - EXECUTION_TIMEOUT=1800    # 30 minutes
  - MAX_NOTEBOOK_SIZE_MB=20   # Larger notebooks
```

## Security Notes

This stack is optimized for homelab/internal use with several built-in security measures:

### Network Security

- Services only bind to localhost by default (change in compose.yaml if needed)
- No external authentication configured (suitable for trusted internal networks)
- Consider adding reverse proxy with SSL/TLS if exposing to wider network

### Application Security  

- **Kernel Whitelist**: Only Python kernels allowed for execution
- **Size Limits**: 5MB request/notebook size limit (configurable)
- **Execution Timeouts**: Prevents runaway processes (300s default)
- **Input Validation**: Notebook JSON validation before execution
- **Temporary Execution**: Notebooks run in ephemeral temporary directories

### Recommended Practices

- Keep Docker engine and images updated regularly
- Change default Jupyter token in environment variables
- Monitor resource usage via metrics endpoint
- Backup notebook data regularly
- Use specific image tags instead of `latest` for production

### For Internet Exposure

If you need to expose these services to the internet:

1. Add authentication/authorization layer (reverse proxy recommended)
2. Enable HTTPS/SSL termination  
3. Consider VPN access instead of direct exposure
4. Implement rate limiting and request size restrictions
5. Regular security updates and monitoring

## License

This project is open-source and available under the MIT License.