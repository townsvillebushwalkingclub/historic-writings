# PDF OCR with LLMs AI

This script converts PDF files to images and performs OCR (Optical Character Recognition) using Google's Gemini Pro 2.5 model. It includes comprehensive error handling, rate limit management, and progress saving capabilities.

## Features

- ✅ Converts PDF pages to high-quality images
- ✅ Uses Google Gemini Pro 2.5 for accurate OCR
- ✅ Handles handwritten and printed typewriter text
- ✅ Comprehensive error handling and retry logic
- ✅ Rate limit detection and graceful stopping
- ✅ Progress saving and resumption capabilities
- ✅ Page-by-page processing with page breaks
- ✅ UTF-8 encoding support for special characters
- ✅ Converts to markdown

## Prerequisites

1. **Python 3.7 or higher**
2. **Google API Key** - Get one from [Google AI Studio](https://makersuite.google.com/app/apikey)
3. **PDF files** - Place them in the `pdfs/` folder

## Installation

1. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

2. Set up your Google API key:

   - Create a `.env` file in the project root
   - Add your API key:

```text
GOOGLE_API_KEY=your_actual_api_key_here
```

## Usage

1. **Place PDF files** in the `pdfs/` folder
2. **Run the script**:

    ```bash
    python pdf_ocr_gemini.py
    ```

3. **Monitor progress** - The script will:

   - Process PDFs in alphabetical order
   - Show progress for each page
   - Save OCR results to `ocr_output/` folder
   - Handle errors gracefully

4. **Resume processing** - If the script stops due to rate limits:

     - Wait for the next day (rate limits reset daily)
     - Run the script again
     - It will automatically resume from where it left off

## Docker Setup (Automated)

For automated processing every 12 hours, you can use Docker:

### Quick Start

```bash
# 1. Set up environment
echo "GOOGLE_API_KEY=your_api_key_here" > .env

# 2. Start the service
docker-compose up -d

# 3. Monitor logs
docker-compose logs -f pdf-ocr
```

### Docker Commands

```bash
# Start service (runs every 12 hours)
docker-compose up -d

# Run once and exit
docker-compose run --rm pdf-ocr run

# Monitor logs
docker-compose logs -f pdf-ocr

# Check status
docker-compose ps

# Stop service
docker-compose down
```

## Output

For each PDF file `example.pdf`, the script creates:

- `ocr_output/example_ocr.txt` - Contains OCR text with page breaks

Example output format:

```text
=== OCR Results for example.pdf ===
Generated on: 2024-01-15 10:30:45

--- Page 1 ---
[OCR text from page 1]

==================================================

--- Page 2 ---
[OCR text from page 2]

==================================================
```

## Error Handling

The script handles various error scenarios:

- **Rate Limits (429)**: Stops gracefully and saves progress
- **Service Unavailable (503)**: Retries with exponential backoff
- **Internal Errors (500)**: Retries with exponential backoff
- **Network Issues**: Continues with next page/file
- **Ctrl+C**: Saves progress before exiting

## Progress Tracking

Progress is automatically saved to `ocr_progress.json`:

- Tracks processed pages for each PDF
- Allows resumption after interruptions
- Stores completion status and timestamps

## Rate Limits

Google Gemini has daily rate limits:

- The script automatically detects rate limit errors
- Saves progress and stops gracefully
- You can resume the next day

## Configuration

You can modify these settings in the script:

```python
GEMINI_MODEL = "gemini-2.5-pro"          # AI model to use
DELAY_BETWEEN_REQUESTS = 2               # Seconds between API calls
MAX_RETRIES = 3                          # Retry attempts for errors
RETRY_DELAY = 5                          # Seconds between retries
```

## Troubleshooting

### Common Issues

1. **"Missing GOOGLE_API_KEY"**
   - Ensure `.env` file exists with your API key
   - Check the API key is valid

2. **"No PDF files found"**
   - Verify PDFs are in the `pdfs/` folder
   - Check file extensions are `.pdf`

3. **Rate limit errors**
   - Wait for the next day
   - Run the script again to resume

4. **Memory issues with large PDFs**
   - The script processes one page at a time
   - Large images are automatically resized

### Support

If you encounter issues:

1. Check the console output for error messages
2. Verify your API key is valid
3. Ensure you have sufficient API quota
4. Check the `ocr_progress.json` file for processing status

## PDF Compression

If your PDF files are large (over 5MB), you can use the included compression script to reduce their size before OCR processing:

```bash
python pdf_compressor.py
```

**Note**: Use `pdf_compressor.py` - this is the reliable version that works without errors.

### Compression Features

- **Safe Processing**: Original files remain unchanged in `pdfs/` folder
- **Compressed Output**: Creates optimized files in `pdfs_compressed/` folder
- **Smart Processing**: Compresses files over 5MB, copies smaller files
- **Gentle Compression**: Uses multiple strategies to reduce size while maintaining quality
- **Progress Feedback**: Shows before/after sizes and compression ratios

### Compression Methods

1. **Basic Compression**: PDF structure optimization and stream compression
2. **Image Compression**: Reduces large embedded images
3. **Aggressive Mode**: Converts pages to optimized images (last resort)

The script will automatically detect which files need compression and guide you through the process. **Your original files in `pdfs/` remain untouched** - all compressed/optimized files are saved in the new `pdfs_compressed/` folder.
