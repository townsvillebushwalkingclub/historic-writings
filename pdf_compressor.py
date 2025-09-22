#!/usr/bin/env python3
"""
Simple PDF Compression Script
Compresses PDF files over 5MB using basic but reliable methods
"""

import os
import sys
import shutil
import uuid
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF

# Configuration
PDFS_FOLDER = "pdfs"
COMPRESSED_FOLDER = "pdfs_compressed"
MAX_SIZE_MB = 5.0
MAX_SIZE_BYTES = int(MAX_SIZE_MB * 1024 * 1024)  # 5MB in bytes

def get_file_size_mb(file_path):
    """Get file size in MB"""
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024), size_bytes

def get_output_path(source_path, compressed_folder):
    """Get the output path for compressed file"""
    try:
        os.makedirs(compressed_folder, exist_ok=True)
        filename = os.path.basename(source_path)
        output_path = os.path.join(compressed_folder, filename)
        return output_path
    except Exception as e:
        print(f"  ✗ Failed to create compressed folder: {e}")
        return None

def compress_pdf_simple(input_path, output_path):
    """
    Simple PDF compression using basic PyMuPDF methods
    
    Args:
        input_path (str): Path to input PDF
        output_path (str): Path for output PDF
        
    Returns:
        tuple: (success, final_size_mb, compression_ratio)
    """
    # Create temporary output file
    temp_path = input_path + f".temp_{uuid.uuid4().hex[:8]}"
    
    try:
        print(f"    Opening PDF...")
        # Open the PDF document
        doc = fitz.open(input_path)
        print(f"    Pages: {len(doc)}")
        
        # Method 1: Basic compression
        print(f"    Applying basic compression...")
        doc.save(
            temp_path,
            garbage=4,          # Remove unused objects
            deflate=True,       # Compress streams
            clean=True,         # Clean up structure
            ascii=False,        # Keep binary encoding
            expand=0,           # Don't expand images
            linear=False,       # Don't linearize
        )
        doc.close()
        
        basic_size = os.path.getsize(temp_path)
        print(f"    Basic compression: {basic_size / (1024*1024):.2f} MB")
        
        # Method 2: If still too large, try image-to-PDF conversion (aggressive)
        if basic_size > MAX_SIZE_BYTES:
            print(f"    Trying aggressive compression...")
            
            # Reopen the document
            doc = fitz.open(input_path)
            
            # Create new document with compressed pages
            new_doc = fitz.open()
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Convert page to image with lower resolution and quality
                mat = fitz.Matrix(1.0, 1.0)  # Standard resolution
                pix = page.get_pixmap(matrix=mat)
                
                # Get JPEG data with compression
                img_data = pix.tobytes("jpeg", jpg_quality=60)  # Lower quality
                
                # Create new page with same dimensions
                rect = page.rect
                new_page = new_doc.new_page(width=rect.width, height=rect.height)
                
                # Insert the compressed image
                new_page.insert_image(rect, stream=img_data)
            
            # Close original and save new
            doc.close()
            
            # Save to a different temp file
            aggressive_temp = temp_path + "_aggressive"
            new_doc.save(aggressive_temp)
            new_doc.close()
            
            aggressive_size = os.path.getsize(aggressive_temp)
            print(f"    Aggressive compression: {aggressive_size / (1024*1024):.2f} MB")
            
            # Use the better result
            if aggressive_size < basic_size:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                os.rename(aggressive_temp, temp_path)
                final_size = aggressive_size
                print(f"    Using aggressive compression result")
            else:
                if os.path.exists(aggressive_temp):
                    os.remove(aggressive_temp)
                final_size = basic_size
                print(f"    Using basic compression result")
        else:
            final_size = basic_size
        
        # Calculate results
        original_size = os.path.getsize(input_path)
        final_size_mb = final_size / (1024 * 1024)
        compression_ratio = (original_size - final_size) / original_size * 100
        
        # Move to output location
        shutil.move(temp_path, output_path)
        
        return True, final_size_mb, compression_ratio
        
    except Exception as e:
        print(f"    ✗ Compression failed: {e}")
        
        # Clean up temp files
        for temp_file in [temp_path, temp_path + "_aggressive"]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        return False, 0, 0

def process_pdf_file(pdf_path):
    """Process a single PDF file"""
    filename = os.path.basename(pdf_path)
    size_mb, size_bytes = get_file_size_mb(pdf_path)
    
    print(f"\n📄 {filename}")
    print(f"   Current size: {size_mb:.2f} MB")
    
    # Get output path for compressed file
    output_path = get_output_path(pdf_path, COMPRESSED_FOLDER)
    if not output_path:
        print(f"   ✗ Failed to create output path")
        return False
    
    # Check if compressed file already exists
    if os.path.exists(output_path):
        compressed_size_mb, _ = get_file_size_mb(output_path)
        print(f"   ✓ Compressed version already exists: {compressed_size_mb:.2f} MB")
        return True
    
    if size_bytes <= MAX_SIZE_BYTES:
        print(f"   ✓ Size is already under {MAX_SIZE_MB} MB - copying to compressed folder")
        try:
            shutil.copy2(pdf_path, output_path)
            print(f"   ✓ Copied to: {output_path}")
            return True
        except Exception as e:
            print(f"   ✗ Failed to copy file: {e}")
            return False
    
    print(f"   ⚠ Size exceeds {MAX_SIZE_MB} MB - compressing...")
    
    # Compress the PDF
    success, final_size_mb, compression_ratio = compress_pdf_simple(pdf_path, output_path)
    
    if success:
        print(f"   ✓ Compression successful!")
        print(f"   📉 Size reduced: {size_mb:.2f} MB → {final_size_mb:.2f} MB ({compression_ratio:.1f}% reduction)")
        print(f"   💾 Saved to: {output_path}")
        
        if final_size_mb <= MAX_SIZE_MB:
            print(f"   🎯 Target achieved: Now under {MAX_SIZE_MB} MB")
        else:
            print(f"   ⚠ Still over {MAX_SIZE_MB} MB, but reduced as much as possible")
        
        return True
    else:
        print(f"   ✗ Compression failed")
        return False

def main():
    """Main function"""
    print("Simple PDF Compression Script")
    print("=" * 50)
    print(f"Target: Compress PDFs over {MAX_SIZE_MB} MB")
    print(f"Output folder: {COMPRESSED_FOLDER}")
    print("=" * 50)
    
    # Check if PDFs folder exists
    if not os.path.exists(PDFS_FOLDER):
        print(f"✗ PDFs folder '{PDFS_FOLDER}' not found")
        return
    
    # Get list of PDF files
    pdf_files = [f for f in os.listdir(PDFS_FOLDER) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print(f"No PDF files found in '{PDFS_FOLDER}' folder")
        return
    
    pdf_files.sort()
    
    # Show initial analysis
    files_to_process = []
    total_size = 0
    
    print("\n📊 File Size Analysis:")
    for pdf_file in pdf_files:
        pdf_path = os.path.join(PDFS_FOLDER, pdf_file)
        size_mb, size_bytes = get_file_size_mb(pdf_path)
        total_size += size_bytes
        
        # Check if compressed version already exists
        output_path = get_output_path(pdf_path, COMPRESSED_FOLDER)
        if output_path and os.path.exists(output_path):
            compressed_size_mb, _ = get_file_size_mb(output_path)
            status = f"✓ ALREADY COMPRESSED ({compressed_size_mb:.2f} MB)"
        elif size_bytes > MAX_SIZE_BYTES:
            status = "⚠ NEEDS COMPRESSION"
            files_to_process.append(pdf_file)
        else:
            status = "📋 WILL COPY (under 5MB)"
            files_to_process.append(pdf_file)
            
        print(f"   {pdf_file}: {size_mb:.2f} MB - {status}")
    
    print(f"\nSummary:")
    print(f"   Total files: {len(pdf_files)}")
    print(f"   Files to process: {len(files_to_process)}")
    print(f"   Total size: {total_size / (1024*1024):.2f} MB")
    
    if not files_to_process:
        print(f"\n🎉 All files are already processed in the compressed folder!")
        return
    
    # Ask for confirmation
    print(f"\n📁 Compressed files will be saved to '{COMPRESSED_FOLDER}' folder")
    print(f"📁 Original files in '{PDFS_FOLDER}' will remain unchanged")
    response = input(f"\nProceed with processing {len(files_to_process)} files? (y/n): ").strip().lower()
    
    if response != 'y':
        print("Operation cancelled by user")
        return
    
    # Process files
    print(f"\n🔄 Processing {len(files_to_process)} files...")
    
    successful = 0
    failed = 0
    
    for i, pdf_file in enumerate(files_to_process, 1):
        pdf_path = os.path.join(PDFS_FOLDER, pdf_file)
        print(f"\n[{i}/{len(files_to_process)}] Processing...")
        
        if process_pdf_file(pdf_path):
            successful += 1
        else:
            failed += 1
    
    # Final summary
    print(f"\n{'='*50}")
    print("PROCESSING SUMMARY")
    print(f"{'='*50}")
    print(f"Successfully processed: {successful}")
    print(f"Failed: {failed}")
    
    if successful > 0:
        print(f"\n✓ Compressed files saved in: {COMPRESSED_FOLDER}")
        print(f"✓ Original files remain unchanged in: {PDFS_FOLDER}")
        print(f"✓ Use the files in '{COMPRESSED_FOLDER}' for OCR processing")
    
    print(f"\n🎉 Processing complete!")

if __name__ == "__main__":
    main()
