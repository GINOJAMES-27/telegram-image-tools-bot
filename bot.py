from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from PIL import Image
import os
import img2pdf
# Changed import to use modern pypdf syntax
from pypdf import PdfWriter

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Ensure local directories exist before running
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🖼 Image Conversion", callback_data="convert")],
        [InlineKeyboardButton("🗜 Image Compressor", callback_data="compress")],
        [InlineKeyboardButton("📄 Image to PDF", callback_data="pdf")],
        [InlineKeyboardButton("🧩 Merge PDFs", callback_data="merge_pdf_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🖼 Welcome to Image Tools Bot\n\nChoose an option:",
        reply_markup=reply_markup
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # IMAGE CONVERSION
    if query.data == "convert":
        keyboard = [
            [InlineKeyboardButton("PNG", callback_data="format_png")],
            [InlineKeyboardButton("JPEG", callback_data="format_jpeg")],
            [InlineKeyboardButton("WEBP", callback_data="format_webp")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Choose output format:", reply_markup=reply_markup)

    elif query.data.startswith("format_"):
        selected_format = query.data.replace("format_", "")
        user_state[user_id] = {
            "action": "convert",
            "format": selected_format
        }
        await query.edit_message_text(
            f"Selected format: {selected_format.upper()}\n\nNow upload an image."
        )

    # IMAGE COMPRESSOR
    elif query.data == "compress":
        keyboard = [
            [InlineKeyboardButton("🟢 Low Compression", callback_data="compress_80")],
            [InlineKeyboardButton("🟡 Medium Compression", callback_data="compress_50")],
            [InlineKeyboardButton("🔴 High Compression", callback_data="compress_25")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Choose compression level:", reply_markup=reply_markup)

    elif query.data.startswith("compress_"):
        quality = int(query.data.replace("compress_", ""))
        user_state[user_id] = {
            "action": "compress",
            "quality": quality
        }
        await query.edit_message_text(
            f"Compression Quality: {quality}\n\nNow upload an image."
        )

    # IMAGE TO PDF
    elif query.data == "pdf":
        user_state[user_id] = {
            "action": "pdf",
            "images": []
        }
        keyboard = [[InlineKeyboardButton("✅ Generate PDF", callback_data="generate_pdf")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📄 Upload images one by one.\n\nWhen finished click Generate PDF.",
            reply_markup=reply_markup
        )

    elif query.data == "generate_pdf":
        if user_id not in user_state or user_state[user_id]["action"] != "pdf":
            await query.message.reply_text("No active PDF session found. Start over.")
            return

        images = user_state[user_id]["images"]
        if not images:
            await query.message.reply_text("Please upload at least one image.")
            return

        pdf_path = f"outputs/{user_id}.pdf"
        try:
            with open(pdf_path, "wb") as pdf_file:
                pdf_file.write(img2pdf.convert(images))

            with open(pdf_path, "rb") as pdf_file:
                await query.message.reply_document(document=pdf_file)
            
            await query.message.reply_text("✅ PDF generated successfully.")
        except Exception as e:
            await query.message.reply_text(f"Error generating PDF: {str(e)}")
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            for image in images:
                if os.path.exists(image):
                    os.remove(image)
            user_state.pop(user_id, None)

    # MERGE PDFs MENU
    elif query.data == "merge_pdf_menu":
        user_state[user_id] = {
            "action": "merge_pdf",
            "pdfs": []
        }
        keyboard = [[InlineKeyboardButton("🧩 Merge PDFs", callback_data="execute_merge")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📄 Upload PDF files one by one.\n\nWhen finished click Merge PDFs.",
            reply_markup=reply_markup
        )

    # EXECUTE PDF MERGER
    elif query.data == "execute_merge":
        if user_id not in user_state or user_state[user_id]["action"] != "merge_pdf":
            await query.message.reply_text("No active Merge session found. Start over.")
            return

        pdfs = user_state[user_id]["pdfs"]
        if len(pdfs) < 2:
            await query.message.reply_text("Please upload at least two PDF files to merge.")
            return

        merged_path = f"outputs/{user_id}_merged.pdf"
        try:
            # Replaced PdfMerger() with modern PdfWriter() implementation
            merger = PdfWriter()
            for pdf in pdfs:
                merger.append(pdf)
            
            # PdfWriter writes to a destination file path directly
            merger.write(merged_path)
            merger.close()

            with open(merged_path, "rb") as pdf_file:
                await query.message.reply_document(document=pdf_file)
            
            await query.message.reply_text("✅ PDFs merged successfully.")
        except Exception as e:
            await query.message.reply_text(f"Error merging PDFs: {str(e)}")
        finally:
            if os.path.exists(merged_path):
                os.remove(merged_path)
            for pdf in pdfs:
                if os.path.exists(pdf):
                    os.remove(pdf)
            user_state.pop(user_id, None)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_id = update.message.message_id

    if user_id not in user_state:
        await update.message.reply_text("Please select a tool first.")
        return

    user_data = user_state[user_id]
    action = user_data["action"]
    
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()

    input_path = f"uploads/{user_id}_{message_id}.jpg"
    output_path = None

    try:
        if action == "pdf":
            await photo_file.download_to_drive(input_path)
            user_data["images"].append(input_path)
            image_count = len(user_data["images"])
            
            await update.message.reply_text(
                f"✅ Image {image_count} added.\n"
                f"Current images: {image_count}\n\n"
                f"Upload more images or click the 'Generate PDF' button above."
            )
            return

        await photo_file.download_to_drive(input_path)
        img = Image.open(input_path)

        # IMAGE CONVERSION
        if action == "convert":
            target_format = user_data["format"]
            output_path = f"outputs/{user_id}_{message_id}.{target_format}"
            if target_format == "jpeg":
                img = img.convert("RGB")
            img.save(output_path)

        # IMAGE COMPRESSION
        elif action == "compress":
            quality = user_data["quality"]
            output_path = f"outputs/{user_id}_{message_id}_compressed.jpg"
            img = img.convert("RGB")
            img.save(output_path, optimize=True, quality=quality)
        
        else:
            await update.message.reply_text("Feature not implemented.")
            return

        with open(output_path, "rb") as file:
            await update.message.reply_document(document=file)
        
        await update.message.reply_text("✅ Processing completed.")
        user_state.pop(user_id, None)

    except Exception as e:
        await update.message.reply_text(f"Error processing image: {str(e)}")
    
    finally:
        if action != "pdf":  
            if os.path.exists(input_path):
                os.remove(input_path)
            if output_path and os.path.exists(output_path):
                os.remove(output_path)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_id = update.message.message_id

    if user_id not in user_state:
        await update.message.reply_text("Please select a tool first.")
        return

    user_data = user_state[user_id]
    action = user_data["action"]

    if action == "merge_pdf":
        doc = update.message.document
        
        if doc.mime_type != "application/pdf" and not doc.file_name.lower().endswith('.pdf'):
            await update.message.reply_text("❌ Please upload a valid PDF document.")
            return

        pdf_file = await doc.get_file()
        input_path = f"uploads/{user_id}_{message_id}.pdf"
        
        try:
            await pdf_file.download_to_drive(input_path)
            user_data["pdfs"].append(input_path)
            pdf_count = len(user_data["pdfs"])

            await update.message.reply_text(
                f"✅ PDF {pdf_count} added.\n"
                f"Current PDFs: {pdf_count}\n\n"
                f"Upload more PDFs or click the 'Merge PDFs' button above."
            )
        except Exception as e:
            await update.message.reply_text(f"Error saving PDF: {str(e)}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()