import os
import logging
import tempfile
import shutil
import subprocess
from pathlib import Path
from flask import Flask, request, send_file, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
SUPPORTED_PRECISIONS = ['fp16', 'fp32', 'int4', 'int8']
SUPPORTED_EXECUTION_PROVIDERS = ['cpu', 'cuda', 'rocm', 'dml', 'webgpu', 'NvTensorRtRtx']
MAX_MODEL_SIZE = 50 * 1024 * 1024 * 1024  # 50GB limit
TEMP_DIR = '/app/tmp'
OUTPUT_DIR = '/app/outputs'

# Valid precision + execution provider combinations (from error message)
VALID_COMBINATIONS = [
    ('fp32', 'cpu'), ('fp32', 'cuda'),
    ('fp16', 'cuda'), ('fp16', 'dml'), ('fp16', 'NvTensorRtRtx'),
    ('bf16', 'cuda'),
    ('int4', 'cpu'), ('int4', 'cuda'), ('int4', 'dml'), ('int4', 'webgpu')
]

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for container orchestration"""
    return jsonify({"status": "healthy", "service": "onnx-model-generator"}), 200

@app.route('/generate', methods=['POST'])
def generate_model():
    """Generate ONNX model from HuggingFace model"""
    try:
        # Validate request
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        params = request.get_json()
        model_name = params.get('model')
        precision = params.get('precision', 'fp32')
        execution_provider = params.get('execution_provider', 'cpu')
        hf_token = params.get('token')  # Optional HuggingFace token
        
        # Validate required parameters
        if not model_name:
            return jsonify({"error": "model parameter is required"}), 400
        
        # Validate precision
        if precision not in SUPPORTED_PRECISIONS:
            return jsonify({
                "error": f"Unsupported precision: {precision}. Supported: {SUPPORTED_PRECISIONS}"
            }), 400
        
        # Validate execution provider
        if execution_provider not in SUPPORTED_EXECUTION_PROVIDERS:
            return jsonify({
                "error": f"Unsupported execution_provider: {execution_provider}. Supported: {SUPPORTED_EXECUTION_PROVIDERS}"
            }), 400
        
        # Validate precision + execution provider combination
        if (precision, execution_provider) not in VALID_COMBINATIONS:
            return jsonify({
                "error": f"Invalid combination: {precision} + {execution_provider}. Valid combinations: {VALID_COMBINATIONS}"
            }), 400
        
        logger.info(f"Generating ONNX model for {model_name} with precision {precision} and execution provider {execution_provider}")
        
        # Create temporary directory for this request
        with tempfile.TemporaryDirectory(dir=TEMP_DIR) as temp_dir:
            output_path = os.path.join(temp_dir, 'model_output')
            
            # Build the command
            command = [
                "python", "-m", "onnxruntime_genai.models.builder",
                "--model", model_name,
                "--precision", precision,
                "--execution_provider", execution_provider,
                "--output", output_path
            ]
            
            # Don't add --token parameter at all, use only environment variables
            logger.info(f"Executing command: {' '.join(command)}")
            
            # Set environment variables for HuggingFace
            env = os.environ.copy()
            if hf_token:
                env['HF_TOKEN'] = hf_token
                env['HUGGING_FACE_HUB_TOKEN'] = hf_token
            else:
                # Try to bypass token requirements for public models
                env['HF_HUB_DISABLE_TELEMETRY'] = '1'
                env['TRANSFORMERS_OFFLINE'] = '0'  # Ensure we can download
                env['HF_HUB_OFFLINE'] = '0'  # Ensure we can download
            
            # Execute the model generation
            try:
                result = subprocess.run(
                    command, 
                    check=True, 
                    capture_output=True, 
                    text=True,
                    timeout=1800,  # 30 minutes timeout
                    env=env
                )
                
                logger.info(f"Model generation completed successfully")
                logger.debug(f"Command output: {result.stdout}")
                
            except subprocess.TimeoutExpired:
                logger.error("Model generation timed out")
                return jsonify({"error": "Model generation timed out (30 minutes limit)"}), 408
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Model generation failed: {e.stderr}")
                return jsonify({
                    "error": "Model generation failed",
                    "details": e.stderr,
                    "stdout": e.stdout
                }), 500
            
            # Check if output directory exists and has content
            if not os.path.exists(output_path) or not os.listdir(output_path):
                logger.error("No output generated")
                return jsonify({"error": "No output generated from model conversion"}), 500
            
            # Create archive of the output
            archive_name = f"{model_name.replace('/', '_')}_{precision}_{execution_provider}"
            archive_path = os.path.join(temp_dir, archive_name)
            
            try:
                shutil.make_archive(archive_path, 'zip', output_path)
                archive_file = f"{archive_path}.zip"
                
                if not os.path.exists(archive_file):
                    logger.error("Archive creation failed")
                    return jsonify({"error": "Failed to create output archive"}), 500
                
                logger.info(f"Archive created successfully: {archive_file}")
                
                # Return the zip file
                return send_file(
                    archive_file,
                    as_attachment=True,
                    download_name=f"{archive_name}.zip",
                    mimetype='application/zip'
                )
                
            except Exception as e:
                logger.error(f"Archive creation error: {str(e)}")
                return jsonify({"error": f"Archive creation failed: {str(e)}"}), 500
                
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/models', methods=['GET'])
def list_supported_models():
    """List supported model types, precisions, and execution providers"""
    return jsonify({
        "supported_precisions": SUPPORTED_PRECISIONS,
        "supported_execution_providers": SUPPORTED_EXECUTION_PROVIDERS,
        "valid_combinations": VALID_COMBINATIONS,
        "examples": [
            "microsoft/DialoGPT-medium",
            "microsoft/DialoGPT-small",
            "microsoft/phi-2",
            "meta-llama/Llama-3.2-1B-Instruct",
            "gpt2"
        ],
        "note": "Any HuggingFace model compatible with onnxruntime-genai should work",
        "default_execution_provider": "cpu",
        "token_info": "Some models require a HuggingFace token. Pass it as 'token' parameter in the request."
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
