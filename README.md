# Homelab Jupyter Notebook Server

This repository contains a Docker Compose configuration for running a Jupyter Notebook server optimized for homelab environments.

## Features

- 🚀 JupyterLab enabled by default
- 🔒 Secure token-based authentication
- 📊 Resource management with memory and CPU limits
- 🔄 Automatic container restart on failure
- 🏥 Container health monitoring
- 📁 Persistent storage for notebooks
- 🔌 Isolated network configuration
- 🏷️ Proper container labeling for management

## Prerequisites

- Docker Engine 20.10.0+
- Docker Compose V2
- 4GB+ available RAM
- 2+ CPU cores recommended

## Quick Start

1. Clone this repository:
```bash
git clone <your-repo-url>
cd <repo-directory>
```

2. Create a `.env` file with your configuration:
```bash
JUPYTER_TOKEN=your-secure-token
NB_UID=1000  # Your user ID
NB_GID=100   # Your group ID
```

3. Create the notebooks directory:
```bash
mkdir notebooks
```

4. Start the Jupyter server:
```bash
docker compose up -d
```

5. Access JupyterLab at: http://localhost:8889
   - Use the token you configured in the `.env` file

## Configuration

### Environment Variables

- `JUPYTER_TOKEN`: Authentication token for accessing Jupyter (required)
- `NB_UID`: User ID for the Jupyter user (default: 1000)
- `NB_GID`: Group ID for the Jupyter user (default: 100)
- `JUPYTER_ENABLE_LAB`: Enables JupyterLab interface (default: yes)

### Resource Limits

The container is configured with the following resource constraints:

- Memory:
  - Maximum: 4GB
  - Reserved: 1GB
- CPU:
  - Maximum: 2 cores
  - Reserved: 0.5 cores

### Persistent Storage

Two types of persistent storage are configured:

1. Named Volume: `jupyter-data`
   - Location: `/home/jovyan/work`
   - Persists across container restarts
   - Managed by Docker

2. Local Directory: `./notebooks`
   - Location: `/home/jovyan/notebooks`
   - Directly accessible from host
   - Good for backup and version control

### Networking

- Port: 8889 (host) -> 8888 (container)
- Isolated network: `jupyter-net`
- Network driver: bridge

### Health Monitoring

The container is configured with health checks:

- Interval: 30 seconds
- Timeout: 10 seconds
- Retries: 3
- Start period: 30 seconds
- Check method: HTTP request to Jupyter API

## Maintenance

### Updating

To update to the latest Jupyter image:

```bash
docker compose pull
docker compose up -d
```

### Logs

View container logs:

```bash
docker compose logs -f jupyter
```

### Backup

The `notebooks` directory can be backed up directly from the host system. For the named volume:

```bash
docker run --rm -v jupyter-data:/source -v $(pwd)/backup:/backup alpine tar czf /backup/jupyter-data-$(date +%Y%m%d).tar.gz -C /source .
```

## Security Notes

- Change the default token in the `.env` file
- Keep your Docker engine updated
- Regularly update the Jupyter image
- Consider adding SSL/TLS if exposed to the internet

## License

This project is open-source and available under the MIT License.