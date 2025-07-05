# ONNX Model Generator Docker Container

A Docker container for generating ONNX models from HuggingFace models using `onnxruntime-genai`. This service provides a REST API to convert HuggingFace models to ONNX format with various optimization options.

## Features

- **REST API**: Easy-to-use endpoints for model generation
- **Multiple Formats**: Support for different precision levels (fp32, fp16, int4, int8)
- **Multiple Targets**: CPU and GPU optimization support
- **Security**: Non-root user, proper permissions, token-based authentication
- **Health Monitoring**: Health check endpoint for container monitoring

## Prerequisites

- Docker installed on your system
- HuggingFace account and access token (for downloading models)

### Getting a HuggingFace Token

1. Go to [HuggingFace Settings](https://huggingface.co/settings/tokens)
2. Create a new token with "Read" permissions
3. Save the token securely (you'll need it for API calls)

### Setting Up Your Token (Optional)

If you want to create a local token file for testing:

1. Copy the template file: `cp myhftoken.template myhftoken`
2. Edit `myhftoken` and replace `YOUR_TOKEN_HERE` with your actual token
3. The token file is already in `.gitignore` to prevent accidental commits

**Important**: Never commit your actual token to version control!

## Quick Start

### 1. Build the Docker Image

```bash
docker build -t onnx-model-generator-service:latest .
```

### 2. Run the Container

```bash
docker run -d \
  --name onnx-generator \
  -p 8080:8080 \
  onnx-model-generator-service:latest
```

### 3. Test the Service

Check if the service is running:

```bash
curl http://127.0.0.1:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## API Endpoints

### Health Check
- **GET** `/health`
- Returns service status

### List Available Models
- **GET** `/models`
- Returns list of supported model architectures

### Generate ONNX Model
- **POST** `/generate`
- Converts a HuggingFace model to ONNX format

#### Request Body:
```json
{
  "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
  "precision": "fp32",
  "execution_provider": "cpu",
  "token": "hf_your_token_here"
}
```

#### Parameters:
- `model` (required): HuggingFace model identifier
- `precision` (optional): Model precision - `fp32`, `fp16`, `int4`, `int8` (default: `fp32`)
- `execution_provider` (optional): Target execution provider - `cpu`, `cuda`, `dml` (default: `cpu`)
- `token` (required): HuggingFace access token

## Usage Examples

### Generate a Model with Default Settings (fp32)

```bash
curl -X POST http://127.0.0.1:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "precision": "fp32",
    "execution_provider": "cpu",
    "token": "hf_your_token_here"
  }' -o tinyllama_fp32_model.zip
```

### Generate a Quantized Model (Recommended - int4)

```bash
curl -X POST http://127.0.0.1:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "precision": "int4",
    "execution_provider": "cpu",
    "token": "hf_your_token_here"
  }' -o tinyllama_int4_model.zip
```

**Note**: The model is returned as a downloadable zip file. Use the `-o filename.zip` option to save it to your local machine. int4 precision is recommended for smaller file sizes (~636MB vs ~2.5GB for fp32) and faster generation times.

### Check Available Models

```bash
curl http://127.0.0.1:8080/models
```

## Testing the Container

### Method 1: Using curl (Recommended)

1. **Start the container** (if not already running):
   ```bash
   docker run -d --name onnx-generator -p 8080:8080 onnx-model-generator-service:latest
   ```

2. **Test health endpoint**:
   ```bash
   curl http://127.0.0.1:8080/health
   ```

3. **Test model generation** (replace `your_token` with your actual HuggingFace token):
   ```bash
   curl -X POST http://127.0.0.1:8080/generate \
     -H "Content-Type: application/json" \
     -d '{
       "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
       "precision": "int4",
       "execution_provider": "cpu",
       "token": "hf_your_token_here"
     }' -o test_model.zip
   ```
   
   **Expected result**: A ~636MB zip file containing the ONNX model will be downloaded to your local machine. Generation takes approximately 2-3 minutes.

### Method 2: Using Python Test Script

Create a test script:

```python
import requests
import json

# Test configuration
BASE_URL = "http://127.0.0.1:8080"
TOKEN = "hf_your_token_here"  # Replace with your token

# Test health endpoint
response = requests.get(f"{BASE_URL}/health")
print(f"Health check: {response.status_code} - {response.json()}")

# Test model generation
payload = {
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "precision": "int4",
    "execution_provider": "cpu",
    "token": TOKEN
}

response = requests.post(f"{BASE_URL}/generate", json=payload)
if response.status_code == 200:
    # Save the model zip file
    with open("tinyllama_int4_model.zip", "wb") as f:
        f.write(response.content)
    print(f"Model generation successful! Downloaded {len(response.content)} bytes")
else:
    print(f"Model generation failed: {response.status_code} - {response.text}")
```

## Model Download and Storage

### Downloaded Models

When you generate a model, it's returned as a zip file containing:
- ONNX model files (`.onnx`)
- Configuration files
- Tokenizer files
- All necessary components to run the model

### File Sizes (TinyLlama-1.1B-Chat-v1.0 example)
- **int4 precision**: ~636MB (recommended)
- **fp32 precision**: ~2.5GB
- **fp16 precision**: ~1.3GB

### Model Location
- **NOT stored in container**: Models are temporary during generation
- **Downloaded to your machine**: The complete model comes as a zip download
- **Ready to use**: Extract the zip and use with onnxruntime

## Container Management

### View Container Logs

```bash
docker logs onnx-generator
```

### Stop the Container

```bash
docker stop onnx-generator
```

### Remove the Container

```bash
docker rm onnx-generator
```

### Access Container Shell (for debugging)

```bash
docker exec -it onnx-generator /bin/bash
```

## Security Considerations

- **Token Security**: Never embed tokens in the Docker image. Always pass them via API parameters.
- **Non-root User**: The container runs as a non-root user (`appuser`) for security.
- **File Permissions**: Proper file permissions are set to prevent unauthorized access.
- **Network**: The service only exposes necessary ports (8080 for API).

## Supported Models

The container supports models compatible with `onnxruntime-genai`. Popular models include:
- TinyLlama models
- Microsoft Phi models
- Llama models
- And many others from HuggingFace

Note: Not all HuggingFace models are supported. The `/models` endpoint can help identify supported architectures.

## Technical Details

### Key Dependencies
- Python 3.13
- onnxruntime-genai 0.8.2
- onnxruntime 1.22.0
- torch 2.4.1
- transformers 4.52.4
- onnx 1.18.0

### Container Specifications
- Base Image: `python:3.13-slim`
- Working Directory: `/app`
- User: `appuser` (non-root)
- Exposed Port: 8080
- Health Check: Built-in endpoint monitoring

## Troubleshooting

### Common Issues

1. **Token Authentication Errors**:
   - Ensure your HuggingFace token has the correct permissions
   - Verify the token is valid and not expired

2. **Model Not Supported**:
   - Check if the model architecture is supported by onnxruntime-genai
   - Try with a known working model like TinyLlama

3. **Out of Memory or Worker Crashes**:
   - **Use int4 precision**: Much smaller memory footprint and faster generation
   - **Try smaller models**: Some models may be too large for available memory
   - **Increase Docker memory limits**: If you need fp32 precision
   - **Check logs**: `docker logs onnx-generator` for specific error messages

4. **Model Generation Fails**:
   - **Large models**: fp32 precision may cause memory issues, try int4 instead
   - **Download timeout**: Generation can take 2-5 minutes, don't cancel early
   - **Use `-o filename.zip`**: Always specify output file for curl downloads

5. **Container Won't Start**:
   - Check Docker logs: `docker logs onnx-generator`
   - Verify port 8080 is not already in use

6. **Connection Refused or Broken**:
   - If using podman, try `127.0.0.1:8080` instead of `localhost:8080`
   - Check if the container is actually running: `docker ps`

### Getting Help

If you encounter issues:
1. **Start with int4 precision**: Most reliable for memory-constrained environments
2. **Check container logs**: `docker logs onnx-generator` for detailed error messages
3. **Verify token permissions**: Ensure your HuggingFace token has read access
4. **Use working command**: Start with the tested TinyLlama int4 example above
5. **Check model compatibility**: Use the `/models` endpoint for supported architectures

### Successful Test Command

This command is tested and works:
```bash
curl -X POST http://127.0.0.1:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "precision": "int4",
    "execution_provider": "cpu",
    "token": "your_token_here"
  }' -o working_model.zip
```

## Development and Contributing

### Repository Setup

When cloning this repository:

1. **Set up your token** (if needed):
   ```bash
   cp myhftoken.template myhftoken
   # Edit myhftoken and add your HuggingFace token
   ```

2. **Build and test**:
   ```bash
   docker build -t onnx-model-generator-service:latest .
   docker run -d --name onnx-generator -p 8080:8080 onnx-model-generator-service:latest
   python test_container.py
   ```

### Security Notes

- **Never commit tokens**: The `.gitignore` file is configured to exclude all token files
- **Use environment variables**: For production, pass tokens via environment variables or API parameters
- **Check commits**: Always verify that no sensitive data is included before pushing

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

This project is provided as-is for educational and development purposes. Please ensure compliance with HuggingFace's terms of service and the licenses of any models you convert. 