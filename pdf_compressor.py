#!/usr/bin/env python3
"""
PDF Compression Script
Gently compresses PDF files over 5MB to reduce their size while maintaining quality
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
import fitz  # PyMuPDF

# Configuration
PDFS_FOLDER = "pdfs"
BACKUP_FOLDER = "pdfs_backup"
MAX_SIZE_MB = 5.0
MAX_SIZE_BYTES = int(MAX_SIZE_MB * 1024 * 1024)  # 5MB in bytes
TARGET_SIZE_BYTES = int(4.8 * 1024 * 1024)  # Target 4.8MB to stay safely under 5MB

def get_file_size_mb(file_path):
    """Get file size in MB"""
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024), size_bytes

def create_backup(source_path, backup_folder):
    """Create a backup of the original file"""
    try:
        os.makedirs(backup_folder, exist_ok=True)
        filename = os.path.basename(source_path)
        backup_path = os.path.join(backup_folder, filename)
        
        # Add timestamp if backup already exists
        if os.path.exists(backup_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(filename)
            backup_path = os.path.join(backup_folder, f"{name}_backup_{timestamp}{ext}")
        
        shutil.copy2(source_path, backup_path)
        print(f"  ✓ Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"  ✗ Failed to create backup: {e}")
        return None

def compress_pdf_gentle(input_path, output_path=None, target_size=TARGET_SIZE_BYTES):
    """
    Gently compress a PDF file using multiple strategies
    
    Args:
        input_path (str): Path to input PDF
        output_path (str): Path for output PDF (if None, overwrites input)
        target_size (int): Target file size in bytes
        
    Returns:
        tuple: (success, final_size_mb, compression_ratio)
    """
    if output_path is None:
        output_path = input_path
    
    temp_path = input_path + ".temp"
    
    try:
        # Open the PDF
        doc = fitz.open(input_path)
        
        print(f"    Original pages: {len(doc)}")
        
        # Strategy 1: Basic compression with deflate and garbage collection
        print("    Trying gentle compression...")
        doc.save(
            temp_path,
            garbage=4,  # Aggressive garbage collection
            deflate=True,  # Compress streams
            clean=True,  # Clean up PDF structure
        )
        
        temp_size = os.path.getsize(temp_path)
        print(f"    After basic compression: {temp_size / (1024*1024):.2f} MB")
        
        # If still too large, try more aggressive compression
        if temp_size > target_size:
            print("    Trying image compression...")
            
            # Reopen the temp file
            doc.close()
            doc = fitz.open(temp_path)
            
            # Strategy 2: Compress images in the PDF
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get all images on the page
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Get image data
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        # Skip if image is already small
                        if len(image_bytes) < 100000:  # Less than 100KB
                            continue
                        
                        # Convert to PIL Image and compress
                        from PIL import Image
                        import io
                        
                        # Load image
                        pil_image = Image.open(io.BytesIO(image_bytes))
                        
                        # Resize if very large
                        max_dimension = 1200
                        if max(pil_image.size) > max_dimension:
                            ratio = max_dimension / max(pil_image.size)
                            new_size = tuple(int(dim * ratio) for dim in pil_image.size)
                            pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
                        
                        # Convert to RGB if needed
                        if pil_image.mode in ['RGBA', 'P']:
                            # Create white background for transparency
                            background = Image.new('RGB', pil_image.size, (255, 255, 255))
                            if pil_image.mode == 'RGBA':
                                background.paste(pil_image, mask=pil_image.split()[-1])
                            else:
                                background.paste(pil_image)
                            pil_image = background
                        elif pil_image.mode != 'RGB':
                            pil_image = pil_image.convert('RGB')
                        
                        # Compress as JPEG
                        compressed_buffer = io.BytesIO()
                        pil_image.save(compressed_buffer, format='JPEG', quality=75, optimize=True)
                        compressed_bytes = compressed_buffer.getvalue()
                        
                        # Only replace if significantly smaller
                        if len(compressed_bytes) < len(image_bytes) * 0.8:
                            # Replace the image
                            doc._getXrefStream(xref, compressed_bytes)
                        
                    except Exception as img_error:
                        print(f"      Warning: Could not compress image {img_index} on page {page_num + 1}: {img_error}")
                        continue
            
            # Save with image compression
            doc.save(
                temp_path,
                garbage=4,
                deflate=True,
                clean=True,
            )
            
            temp_size = os.path.getsize(temp_path)
            print(f"    After image compression: {temp_size / (1024*1024):.2f} MB")
        
        # If still too large, try the most aggressive approach
        if temp_size > target_size:
            print("    Trying aggressive compression...")
            
            doc.close()
            doc = fitz.open(temp_path)
            
            # Strategy 3: Convert pages to images and back (most aggressive)
            new_doc = fitz.open()
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Convert page to image
                mat = fitz.Matrix(1.5, 1.5)  # Reduce resolution slightly
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image for additional compression
                from PIL import Image
                import io
                
                img_data = pix.tobytes("jpeg", jpg_quality=80)
                pil_img = Image.open(io.BytesIO(img_data))
                
                # Save as compressed JPEG
                compressed_buffer = io.BytesIO()
                pil_img.save(compressed_buffer, format='JPEG', quality=75, optimize=True)
                compressed_img_data = compressed_buffer.getvalue()
                
                # Create new page and insert image
                rect = page.rect
                new_page = new_doc.new_page(width=rect.width, height=rect.height)
                new_page.insert_image(rect, stream=compressed_img_data)
            
            # Save the new document
            new_doc.save(
                temp_path,
                garbage=4,
                deflate=True,
                clean=True,
            )
            new_doc.close()
            
            temp_size = os.path.getsize(temp_path)
            print(f"    After aggressive compression: {temp_size / (1024*1024):.2f} MB")
        
        doc.close()
        
        # Calculate compression ratio
        original_size = os.path.getsize(input_path)
        final_size_mb = temp_size / (1024 * 1024)
        compression_ratio = (original_size - temp_size) / original_size * 100
        
        # Move temp file to final location
        if output_path != input_path:
            shutil.move(temp_path, output_path)
        else:
            shutil.move(temp_path, input_path)
        
        return True, final_size_mb, compression_ratio
        
    except Exception as e:
        print(f"    ✗ Compression failed: {e}")
        
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        
        return False, 0, 0

def process_pdf_file(pdf_path):
    """Process a single PDF file"""
    filename = os.path.basename(pdf_path)
    size_mb, size_bytes = get_file_size_mb(pdf_path)
    
    print(f"\n📄 {filename}")
    print(f"   Current size: {size_mb:.2f} MB")
    
    if size_bytes <= MAX_SIZE_BYTES:
        print(f"   ✓ Size is already under {MAX_SIZE_MB} MB - skipping")
        return True
    
    print(f"   ⚠ Size exceeds {MAX_SIZE_MB} MB - compressing...")
    
    # Create backup
    backup_path = create_backup(pdf_path, BACKUP_FOLDER)
    if not backup_path:
        print(f"   ✗ Skipping compression due to backup failure")
        return False
    
    # Compress the PDF
    success, final_size_mb, compression_ratio = compress_pdf_gentle(pdf_path)
    
    if success:
        print(f"   ✓ Compression successful!")
        print(f"   📉 Size reduced: {size_mb:.2f} MB → {final_size_mb:.2f} MB ({compression_ratio:.1f}% reduction)")
        
        if final_size_mb <= MAX_SIZE_MB:
            print(f"   🎯 Target achieved: Now under {MAX_SIZE_MB} MB")
        else:
            print(f"   ⚠ Still over {MAX_SIZE_MB} MB, but reduced as much as possible")
        
        return True
    else:
        print(f"   ✗ Compression failed - restoring from backup")
        try:
            shutil.copy2(backup_path, pdf_path)
            print(f"   ✓ Original file restored")
        except Exception as e:
            print(f"   ✗ Failed to restore backup: {e}")
        return False

def main():
    """Main function"""
    print("PDF Compression Script")
    print("=" * 50)
    print(f"Target: Compress PDFs over {MAX_SIZE_MB} MB")
    print(f"Backup folder: {BACKUP_FOLDER}")
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
    large_files = []
    total_size = 0
    
    print("\n📊 File Size Analysis:")
    for pdf_file in pdf_files:
        pdf_path = os.path.join(PDFS_FOLDER, pdf_file)
        size_mb, size_bytes = get_file_size_mb(pdf_path)
        total_size += size_bytes
        
        status = "⚠ NEEDS COMPRESSION" if size_bytes > MAX_SIZE_BYTES else "✓ OK"
        print(f"   {pdf_file}: {size_mb:.2f} MB - {status}")
        
        if size_bytes > MAX_SIZE_BYTES:
            large_files.append(pdf_file)
    
    print(f"\nSummary:")
    print(f"   Total files: {len(pdf_files)}")
    print(f"   Files needing compression: {len(large_files)}")
    print(f"   Total size: {total_size / (1024*1024):.2f} MB")
    
    if not large_files:
        print(f"\n🎉 All files are already under {MAX_SIZE_MB} MB!")
        return
    
    # Ask for confirmation
    print(f"\n⚠ IMPORTANT: Backups will be created in '{BACKUP_FOLDER}' folder")
    response = input(f"\nProceed with compressing {len(large_files)} files? (y/n): ").strip().lower()
    
    if response != 'y':
        print("Operation cancelled by user")
        return
    
    # Process large files
    print(f"\n🔄 Processing {len(large_files)} files...")
    
    successful = 0
    failed = 0
    
    for i, pdf_file in enumerate(large_files, 1):
        pdf_path = os.path.join(PDFS_FOLDER, pdf_file)
        print(f"\n[{i}/{len(large_files)}] Processing...")
        
        if process_pdf_file(pdf_path):
            successful += 1
        else:
            failed += 1
    
    # Final summary
    print(f"\n{'='*50}")
    print("COMPRESSION SUMMARY")
    print(f"{'='*50}")
    print(f"Successfully compressed: {successful}")
    print(f"Failed: {failed}")
    
    if successful > 0:
        print(f"\n✓ Backups saved in: {BACKUP_FOLDER}")
        print(f"✓ You can delete backups if you're satisfied with the results")
    
    print(f"\n🎉 Compression complete!")

if __name__ == "__main__":
    main()
