import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv
from pypdf import PdfReader
import PIL.Image

# --- NEW SDK IMPORTS ---
from google import genai
from google.genai import types
from google.genai.errors import APIError

# --- Configuration & Initialization ---

load_dotenv()
app = Flask(__name__)

# Global variables for the Gemini client setup
client = None
model = 'gemini-2.5-flash' # Using the model variable as specified in your new logic

# Configure Upload Folder
UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 1. Get API Key from .env file
# NOTE: We keep this variable for the file-based configuration, but the new init function uses it.
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") 


def initialize_gemini_client():
    """Initializes the Gemini client with detailed retry configuration."""
    global client
    global model # Ensure the model variable is accessible
    
    # Define the HttpRetryOptions (using custom settings from your request)
    retry_config = types.HttpRetryOptions(
        attempts=5,
        exp_base=7, # Increased exponential backoff base
        initial_delay=1,
        http_status_codes=[429, 500, 503, 504],
    )

    try:
        if not GEMINI_API_KEY:
            print("⚠️ GOOGLE_API_KEY not found. AI functions disabled.")
            return False

        client = genai.Client(
            api_key=GEMINI_API_KEY,  
            http_options=types.HttpOptions(
                retry_options=retry_config
            )
        )
        print(f"✅ Gemini client initialized successfully. Model: {model}")
        return True
    except Exception as e:
        print(f"❌ Error initializing Gemini client: {e}")
        client = None
        return False


# --- AI HELPER FUNCTIONS ---

def extract_text_from_pdf(pdf_path):
    """Extracts text content from a PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"❌ PDF Error: {e}")
        return None

def analyze_with_gemini(system_instruction, content_parts, json_mode=True):
    """Handles the actual API call to the Gemini model for non-chat requests."""
    if not client:
        return json.dumps({"summary": "Server Error: Gemini client not initialized."})

    try:
        config_params = {}
        if json_mode:
             config_params['response_mime_type'] = "application/json"
             
        # API Call execution
        response = client.models.generate_content(
            model=model, # Use the global model variable
            contents=[system_instruction] + content_parts,
            config=types.GenerateContentConfig(**config_params)
        )
        return response.text

    except APIError as e:
        print(f"❌ API Error: {e}")
        return json.dumps({"summary": "AI Error", "benefits": str(e)})

    except Exception as e:
        print(f"❌ General Error: {e}")
        return json.dumps({"summary": "Processing Error", "benefits": str(e)})

# --- AI ENDPOINT ROUTES ---

@app.route('/analyze', methods=['POST'])
def analyze_scheme():
    """ENDPOINT for Scheme Guide AI (scheme.html) - Calls Gemini for scheme analysis."""
    input_type = request.form.get('input_type')
    content_payload = []

    try:
        # --- 1. HANDLE FILE/TEXT/URL INPUT ---
        if input_type == 'file':
            if 'file_data' not in request.files: return jsonify({"success": False, "error": "No file uploaded"}), 400
            file = request.files['file_data']
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            try:
                if file.filename.lower().endswith('.pdf'):
                    text = extract_text_from_pdf(filepath)
                    content_payload.append(f"PDF Content: {text}")
                elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    img = PIL.Image.open(filepath)
                    content_payload.append(img)
            finally:
                if os.path.exists(filepath): os.remove(filepath)
        elif input_type == 'url':
            content_payload.append(f"Scheme URL: {request.form.get('url_data')}")
        elif input_type == 'text':
            content_payload.append(f"Scheme Info: {request.form.get('text_data')}")

        if not content_payload:
            return jsonify({"success": False, "error": "No content provided."}), 400

        scheme_instruction = """
        You are an expert AI assistant for Indian Government Schemes. 
        Analyze the input and identify the scheme.
        Return ONLY a raw JSON object with these keys:
        {
            "eligibility": "Who can apply? (Bullet points)",
            "benefits": "What do they get?",
            "process": "How to apply? (Step-by-step)",
            "summary": "1-line summary."
        }
        """

        raw_json = analyze_with_gemini(scheme_instruction, content_payload, json_mode=True)
        
        try:
            data = json.loads(raw_json)
            return jsonify({"success": True, "data": data})
        except:
            return jsonify({"success": True, "data": {"summary": "Raw Response", "benefits": raw_json}})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/analyze_fraud', methods=['POST'])
def analyze_fraud():
    """ENDPOINT to handle fraud/fake news form submission (fraud.html)."""
    
    text_input = request.form.get('textInput')
    image_file = request.files.get('imageUpload')
    content_payload = []
    
    if text_input: content_payload.append(f"Content for Verification: {text_input}")
    
    if image_file and image_file.filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename)
        image_file.save(filepath)
        try:
            img = PIL.Image.open(filepath)
            content_payload.append(img)
        finally:
             if os.path.exists(filepath): os.remove(filepath)

    if not content_payload:
        return render_template('fraud.html', initial_data={'error': 'Please provide input for analysis.'})

    fraud_instruction = """
    You are an AI Fake News and Fraud Detection expert. Analyze the provided content. 
    Classify the content into one of three classes: 'Likely_Real', 'Likely_Fake', or 'Unverified___Needs_Caution'.
    
    Return ONLY a raw JSON object with the following keys:
    {
        "result_class": "Likely_Fake|Likely_Real|Unverified___Needs_Caution",
        "result_text": "A brief summary of the finding (2 sentences max).",
        "result_details": "Why this classification was given (e.g., source, language, common scam type)."
    }
    """
    
    raw_json = analyze_with_gemini(fraud_instruction, content_payload, json_mode=True)
    
    try:
        result_data = json.loads(raw_json)
    except:
        result_data = {'result_class': 'Unverified___Needs_Caution', 
                       'result_text': 'AI returned malformed data. Review the raw output.',
                       'result_details': raw_json}

    return render_template('fraud.html', initial_data=result_data)


@app.route('/chat', methods=['POST'])
def chat():
    """Handles chat messages for the Mitra AI assistant."""
    if not client:
        return jsonify({"error": "System not ready. Gemini client failed to initialize."}), 503
    
    data = request.get_json()
    user_message = data.get('message', '').strip()
    history = data.get('history', [])

    if not user_message:
        return jsonify({"response": "Please type a message."})

    # Prepare chat history for the API call
    contents = []
    # System instruction for the chat assistant
    system_instruction = ("You are an expert digital literacy and fake news assistant. "
                          "Your goal is to provide clear, actionable, and verified advice. "
                          "Keep your tone helpful and professional.")
    
    # Add history (alternating user/model roles)
    for entry in history:
        contents.append(types.Content(
            role=entry.get('role', 'user'),  # Default role to 'user' if missing
            parts=[types.Part.from_text(text=entry.get('text', ''))]
        ))
    
    # Add the new user message
    contents.append(types.Content(
        role="user", 
        parts=[types.Part.from_text(text=user_message)]
    ))
    
    try:
        # Use a higher temperature for conversational and informative responses
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7 
            )
        )
        
        return jsonify({"response": response.text})

    except APIError as e:
        error_message = f"API Error (Quota/Rate Limit): {e}"
        print(f"❌ {error_message}")
        return jsonify({"error": "I'm experiencing high traffic. Please try again in a minute."}), 500
    except Exception as e:
        error_message = f"Unexpected Error: {e}"
        print(f"❌ {error_message}")
        return jsonify({"error": "An unknown error occurred."}), 500


# --- PAGE RENDERER ROUTES ---

@app.route('/')
@app.route('/index/')
def index_page():
    """Renders the login/register page (index.html)."""
    return render_template('index.html')

@app.route('/home/')
def home_page():
    """Renders the main dashboard (home.html)."""
    return render_template('home.html')

@app.route('/scheme/')
def scheme_page():
    """Renders the Scheme Guide AI page (scheme.html)."""
    return render_template('scheme.html')

@app.route('/fraud/')
def fraud_page():
    """Renders the Fake/Fraud Detection page (fraud.html) initially."""
    return render_template('fraud.html', initial_data={})

@app.route('/mitra/')
def mitra_page():
    """Renders the Mitra AI page (mitra.html)."""
    # NOTE: The chat logic is separate in /chat, this renders the UI.
    return render_template('mitra.html')


if __name__ == '__main__':
    # Initialize client when the app starts
    if initialize_gemini_client():
        print("\n--- Starting Flask Chat Assistant (http://127.0.0.1:5000/) ---")
        app.run(debug=True)
    else:
        print("\n--- Flask Server NOT Started. Gemini client failed to initialize. ---")