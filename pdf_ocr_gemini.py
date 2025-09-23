#!/usr/bin/env python3
"""
PDF OCR Script using Google Gemini Pro 2.5
Converts PDFs to images and performs OCR using Google's Gemini API
"""

import os
import sys
import json
import time
import signal
import io
import base64
import random
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

# Configuration
def get_random_api_key():
    """Randomly select from GOOGLE_API_KEY array or use single GOOGLE_API_KEY"""
    api_key_env = os.getenv('GOOGLE_API_KEY')
    
    if not api_key_env:
        return None
    
    # Check if it's a JSON array (starts with [ and ends with ])
    if api_key_env.strip().startswith('[') and api_key_env.strip().endswith(']'):
        try:
            # Parse as JSON array
            api_keys = json.loads(api_key_env)
            if isinstance(api_keys, list) and len(api_keys) > 0:
                # Filter out empty strings
                valid_keys = [key for key in api_keys if key and key.strip()]
                if valid_keys:
                    selected_key = random.choice(valid_keys)
                    print(f"Selected API key from array (index {api_keys.index(selected_key)})")
                    return selected_key
                else:
                    print("No valid API keys found in array")
                    return None
            else:
                print("Invalid array format in GOOGLE_API_KEY")
                return None
        except json.JSONDecodeError:
            print("Failed to parse GOOGLE_API_KEY as JSON array, treating as single key")
            return api_key_env
    
    # Single API key
    print("Using single API key")
    return api_key_env

GOOGLE_API_KEY = get_random_api_key()

# Debug: Print API key info (first 10 chars for security)
if GOOGLE_API_KEY:
    print(f"API Key loaded: {GOOGLE_API_KEY[:10]}...")
else:
    print("No API key found!")

GEMINI_MODEL = "gemini-2.5-pro"  # Multimodal model that supports images
PDFS_FOLDER = "pdfs"  # Do not use compressed folder by default
PDFS_FOLDER_FALLBACK = "pdfs_compressed"
OUTPUT_FOLDER = "ocr_output"
PROGRESS_FILE = "ocr_progress.json"

# OCR Prompt
OCR_PROMPT = "You are a powerful OCR and handwriting expert. Please respond with all the words on this page"
#OCR_PROMPT = "You are a powerful OCR and handwriting expert. Please respond with all the words on this page in markdown for a Ghost Pro CMS."

# Rate limiting settings
DELAY_BETWEEN_REQUESTS = 3  # seconds
MAX_RETRIES = 10
RETRY_DELAY = 10  # seconds

# Validate API key
if not GOOGLE_API_KEY:
    raise EnvironmentError("Missing GOOGLE_API_KEY environment variable. Please set it in your .env file.")

# Initialize Google Gemini client
try:
    client = genai.Client(api_key=GOOGLE_API_KEY)
    print(f"Initialized Gemini client with model: {GEMINI_MODEL}")
except Exception as e:
    raise EnvironmentError(f"Failed to initialize Gemini client: {e}")

# Global variables for signal handling
current_pdf = None
processed_files = []
progress_data = {}

def load_progress():
    """Load progress from JSON file"""
    global progress_data
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                print(f"Loaded progress data for {len(progress_data)} files")
        else:
            progress_data = {}
            print("No progress file found, starting fresh")
    except Exception as e:
        print(f"Error loading progress file: {e}")
        progress_data = {}

def save_progress():
    """Save current progress to JSON file"""
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)
        print(f"Progress saved for {len(progress_data)} files")
    except Exception as e:
        print(f"Error saving progress: {e}")

def pdf_to_images(pdf_path):
    """
    Convert PDF pages to images
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        list: List of PIL Image objects, one per page
    """
    images = []
    try:
        # Open the PDF
        pdf_document = fitz.open(pdf_path)
        
        print(f"Converting {len(pdf_document)} pages from {os.path.basename(pdf_path)} to images...")
        
        for page_num in range(len(pdf_document)):
            # Get the page
            page = pdf_document[page_num]
            
            # Convert page to image (higher DPI for better OCR)
            mat = fitz.Matrix(2.0, 2.0)  # 2x scaling for better quality
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            images.append(image)
            print(f"  Converted page {page_num + 1}/{len(pdf_document)}")
        
        pdf_document.close()
        print(f"Successfully converted {len(images)} pages to images")
        return images
        
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        return []

def image_to_base64(image):
    """Convert PIL Image to base64 string"""
    try:
        # Resize if image is too large (Gemini has size limits)
        max_size = 2048
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=85)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return image_base64
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        return None

def ocr_with_gemini(image, page_num, retry_count=0):
    """
    Perform OCR on an image using Gemini API
    
    Args:
        image (PIL.Image): The image to OCR
        page_num (int): Page number for logging
        retry_count (int): Current retry attempt
        
    Returns:
        tuple: (ocr_text, success, should_stop)
            - ocr_text: The extracted text or empty string
            - success: Whether the OCR was successful
            - should_stop: Whether to stop processing due to rate limits
    """
    try:
        # Convert image to base64
        image_base64 = image_to_base64(image)
        if not image_base64:
            return "", False, False
        
        # Prepare content for Gemini API
        contents = [
            OCR_PROMPT,
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_base64
                }
            }
        ]
        
        print(f"  Sending page {page_num} to Gemini for OCR...")
        
        # Call Gemini API
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents
        )
        
        if response.text:
            print(f"  ✓ Successfully extracted text from page {page_num}")
            return response.text.strip(), True, False
        else:
            print(f"  ⚠ Empty response from Gemini for page {page_num}")
            return "", False, False
            
    except Exception as e:
        error_str = str(e)
        
        # Check for invalid API key error (400)
        if '400' in error_str and ('INVALID_ARGUMENT' in error_str or 'API_KEY_INVALID' in error_str or 'API key not valid' in error_str):
            print(f"  ✗ Invalid API key error for page {page_num}. Stopping script.")
            print(f"  Error: {e}")
            return "", False, True  # Signal to stop processing
            
        # Check for rate limit error (429)
        elif '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
            print(f"  ⚠ Rate limit reached for page {page_num}. Stopping script.")
            print(f"  Error: {e}")
            return "", False, True  # Signal to stop processing
            
        # Check for service unavailable (503)
        elif '503' in error_str or 'UNAVAILABLE' in error_str:
            print(f"  ⚠ Service unavailable for page {page_num}")
            if retry_count < MAX_RETRIES:
                print(f"  Retrying in {RETRY_DELAY} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
                return ocr_with_gemini(image, page_num, retry_count + 1)
            else:
                print(f"  ✗ Max retries exceeded for page {page_num}. Stopping script.")
                print(f"  Error: {e}")
                return "", False, True  # Signal to stop processing
                
        # Check for internal server error (500)
        elif '500' in error_str or 'INTERNAL' in error_str:
            print(f"  ⚠ Internal server error for page {page_num}")
            if retry_count < MAX_RETRIES:
                print(f"  Retrying in {RETRY_DELAY} seconds... (attempt {retry_count + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
                return ocr_with_gemini(image, page_num, retry_count + 1)
            else:
                print(f"  ✗ Max retries exceeded for page {page_num}. Stopping script.")
                print(f"  Error: {e}")
                return "", False, True  # Signal to stop processing
        else:
            print(f"  ✗ Error calling Gemini API for page {page_num}: {e}")
            return "", False, False

def process_pdf(pdf_path):
    """
    Process a single PDF file
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        bool: True if processing should continue, False if should stop (rate limit)
    """
    global current_pdf, progress_data
    
    pdf_filename = os.path.basename(pdf_path)
    current_pdf = pdf_filename
    
    print(f"\n{'='*60}")
    print(f"Processing: {pdf_filename}")
    print(f"{'='*60}")
    
    # Check if this PDF was already processed
    if pdf_filename in progress_data and progress_data[pdf_filename].get('completed', False):
        print(f"✓ Skipping {pdf_filename} - already completed")
        return True
    
    # Create output filename
    output_filename = os.path.splitext(pdf_filename)[0] + "_ocr.txt"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)
    
    # Initialize progress for this PDF if needed
    if pdf_filename not in progress_data:
        progress_data[pdf_filename] = {
            'total_pages': 0,
            'processed_pages': 0,
            'completed': False,
            'output_file': output_filename,
            'start_time': datetime.now().isoformat()
        }
    
    try:
        # Convert PDF to images
        images = pdf_to_images(pdf_path)
        if not images:
            print(f"✗ Failed to convert {pdf_filename} to images")
            return True
        
        total_pages = len(images)
        progress_data[pdf_filename]['total_pages'] = total_pages
        
        # Get starting page from progress
        start_page = progress_data[pdf_filename]['processed_pages']
        
        print(f"Total pages: {total_pages}")
        if start_page > 0:
            print(f"Resuming from page {start_page + 1}")
        
        # Open output file in append mode if resuming, write mode if starting fresh
        mode = 'a' if start_page > 0 else 'w'
        
        with open(output_path, mode, encoding='utf-8') as output_file:
            # Process each page starting from where we left off
            for page_num in range(start_page, total_pages):
                current_page = page_num + 1
                
                print(f"\nProcessing page {current_page}/{total_pages}")
                
                # Perform OCR
                ocr_text, success, should_stop = ocr_with_gemini(images[page_num], current_page)
                
                if should_stop:
                    print(f"\n⚠ Rate limit reached. Stopping at page {current_page} of {pdf_filename}")
                    save_progress()
                    return False  # Signal to stop processing
                
                # Write page content to file
                if page_num == 0 and start_page == 0:
                    # First page of a new file
                    output_file.write(f"=== OCR Results for {pdf_filename} ===\n")
                    output_file.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                output_file.write(f"--- Page {current_page} ---\n")
                if success and ocr_text:
                    output_file.write(ocr_text)
                else:
                    output_file.write("[OCR failed or no text detected]")
                output_file.write(f"\n\n{'='*50}\n\n")
                
                # Flush to ensure data is written
                output_file.flush()
                
                # Update progress
                progress_data[pdf_filename]['processed_pages'] = current_page
                
                # Save progress after each page
                save_progress()
                
                # Rate limiting delay
                if current_page < total_pages:  # Don't delay after the last page
                    print(f"  Waiting {DELAY_BETWEEN_REQUESTS} seconds before next request...")
                    time.sleep(DELAY_BETWEEN_REQUESTS)
        
        # Mark as completed
        progress_data[pdf_filename]['completed'] = True
        progress_data[pdf_filename]['completion_time'] = datetime.now().isoformat()
        save_progress()
        
        print(f"\n✓ Successfully processed {pdf_filename}")
        print(f"  Output saved to: {output_path}")
        
        processed_files.append(pdf_filename)
        return True
        
    except Exception as e:
        print(f"\n✗ Error processing {pdf_filename}: {e}")
        save_progress()
        return True  # Continue with next file despite error

def signal_handler(signum, frame):
    """Handle Ctrl+C interruption"""
    print(f"\n\nReceived signal {signum}. Script interrupted by user.")
    print("Saving progress...")
    
    try:
        save_progress()
        print("Progress saved successfully.")
    except Exception as e:
        print(f"Failed to save progress: {e}")
    
    print("Exiting gracefully...")
    sys.exit(0)

def print_summary():
    """Print processing summary"""
    print(f"\n{'='*60}")
    print("PROCESSING SUMMARY")
    print(f"{'='*60}")
    
    total_pdfs = len([f for f in os.listdir(PDFS_FOLDER) if f.lower().endswith('.pdf')])
    completed_pdfs = len([pdf for pdf, data in progress_data.items() if data.get('completed', False)])
    
    print(f"Total PDFs in folder: {total_pdfs}")
    print(f"Completed PDFs: {completed_pdfs}")
    print(f"Remaining PDFs: {total_pdfs - completed_pdfs}")
    
    if processed_files:
        print(f"\nProcessed in this session:")
        for pdf in processed_files:
            print(f"  ✓ {pdf}")
    
    if progress_data:
        print(f"\nDetailed status:")
        for pdf_name, data in progress_data.items():
            status = "✓ Completed" if data.get('completed', False) else f"⏸ {data.get('processed_pages', 0)}/{data.get('total_pages', '?')} pages"
            print(f"  {pdf_name}: {status}")

def main():
    """Main function"""
    try:
        # Set up signal handler for Ctrl+C
        signal.signal(signal.SIGINT, signal_handler)
        
        print("PDF OCR Script using Google Gemini Pro 2.5")
        print("=" * 50)
        
        # Create output directory
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        
        # Load previous progress
        load_progress()
        
        # Get list of PDF files - prefer compressed folder, fallback to original
        pdfs_folder_to_use = PDFS_FOLDER
        if not os.path.exists(PDFS_FOLDER):
            if os.path.exists(PDFS_FOLDER_FALLBACK):
                pdfs_folder_to_use = PDFS_FOLDER_FALLBACK
                print(f"📁 Using original PDFs folder: {PDFS_FOLDER_FALLBACK}")
                print(f"💡 Tip: Run 'python pdf_compressor_simple.py' first to create compressed versions")
            else:
                raise FileNotFoundError(f"Neither '{PDFS_FOLDER}' nor '{PDFS_FOLDER_FALLBACK}' folder found")
        else:
            print(f"📁 Using compressed PDFs folder: {PDFS_FOLDER}")
        
        pdf_files = [f for f in os.listdir(pdfs_folder_to_use) if f.lower().endswith('.pdf')]
        if not pdf_files:
            print(f"No PDF files found in '{pdfs_folder_to_use}' folder")
            return
        
        pdf_files.sort()  # Process in alphabetical order
        
        print(f"Found {len(pdf_files)} PDF files to process")
        
        # Process each PDF
        for i, pdf_file in enumerate(pdf_files, 1):
            pdf_path = os.path.join(pdfs_folder_to_use, pdf_file)
            
            print(f"\n[{i}/{len(pdf_files)}] Starting {pdf_file}")
            
            # Process the PDF
            should_continue = process_pdf(pdf_path)
            
            if not should_continue:
                print(f"\n⚠ Stopping due to rate limit. Progress has been saved.")
                print(f"You can resume processing tomorrow by running this script again.")
                break
        
        # Print final summary
        print_summary()
        
        if progress_data:
            all_completed = all(data.get('completed', False) for data in progress_data.values())
            if all_completed:
                print(f"\n🎉 All PDFs have been successfully processed!")
            else:
                print(f"\n⏸ Processing paused. Run the script again to continue from where you left off.")
        
    except KeyboardInterrupt:
        print(f"\nScript interrupted by user.")
        
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        save_progress()
        raise

if __name__ == "__main__":
    main()
