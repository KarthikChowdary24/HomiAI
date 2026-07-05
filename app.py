from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from google import genai
from groq import Groq
from PIL import Image
import markdown
from datetime import datetime
from flask import send_file
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import re
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = "homiai_secret_key_2026"

# Database Configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///homiai.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Database Table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)

class DesignHistory(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    image_name = db.Column(db.String(200))

    room_type = db.Column(db.String(100))

    style = db.Column(db.String(100))

    ai_provider = db.Column(db.String(100))

    suggestions = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )


# Gemini Client
client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)
# Groq Client
groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# Upload Folder
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Home Page
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(
            request.form["password"]
        )
        existing_user = User.query.filter_by(
            email=email
        ).first()
        if existing_user:
            return "Email already registered."
        new_user = User(
            username=username,
            email=email,
            password=password
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(
            email=email
        ).first()
        if user and check_password_hash(
            user.password,
            password
        ):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect("/")
        return "Invalid email or password."
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# Upload Page
@app.route("/upload")
def upload():

    if "user_id" not in session:
        return redirect("/login")

    return render_template("upload.html")


# Generate AI Suggestions
@app.route("/upload-image", methods=["POST"])
def upload_image():

    image = request.files["roomImage"]
    room_type = request.form["roomType"]
    style = request.form["style"]
    filename = image.filename

    image_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    image.save(image_path)

    room_image = Image.open(image_path)

    prompt = f"""
You are a professional AI Interior Designer.

Analyze the uploaded room image carefully.

Room Type:
{room_type}

Preferred Style:
{style}

Inspect the room and identify:

- Furniture
- Wall colors
- Flooring
- Ceiling
- Lighting
- Space utilization
- Decorations
- Empty areas
- Design problems

Generate a professional interior design report.

Use Markdown.

# 🏠 Room Analysis

## ⭐ Overall Rating

## 📊 Current Condition

## 🎨 Recommended Color Palette

## 🛋 Furniture Recommendations

## 💡 Lighting Improvements

## 🌿 Decor Suggestions

## 💰 Estimated Budget (INR)

## 🎯 Top 5 Improvements

## 🤖 AI Summary
"""

    try:

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                room_image
            ]
        )

        suggestions = response.text

        ai_provider = "Gemini Vision"

    except Exception as e:

        import traceback

        print("Gemini failed:")
        traceback.print_exc()

        fallback_prompt = f"""
You are a professional AI Interior Designer.

The vision service is temporarily unavailable.

Generate a professional interior design report using the information below.

Room Type:
{room_type}

Preferred Style:
{style}

Use the following format.

# 🏠 Room Analysis

## ⭐ Overall Rating

## 📊 Current Condition

## 🎨 Recommended Color Palette

## 🛋 Furniture Recommendations

## 💡 Lighting Improvements

## 🌿 Decor Suggestions

## 💰 Estimated Budget (INR)

## 🎯 Top 5 Improvements

## 🤖 AI Summary

Use Markdown headings and bullet points.
"""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": fallback_prompt
                }
            ]
        )

        suggestions = response.choices[0].message.content

        ai_provider = "Groq Fallback"

    suggestions = markdown.markdown(
        suggestions,
        extensions=["extra"]
    )

    # Save to Database
    design_entry = DesignHistory(
    image_name=filename,
    room_type=room_type,
    style=style,
    ai_provider=ai_provider,
    suggestions=suggestions,
    user_id=session["user_id"]
)

    db.session.add(design_entry)
    db.session.commit()

    return render_template(
    "result.html",
    filename=filename,
    room_type=room_type,
    style=style,
    suggestions=suggestions,
    ai_provider=ai_provider,
    design_id=design_entry.id
)


# History Page
@app.route("/history")
def history():

    if "user_id" not in session:
        return redirect("/login")

    designs = DesignHistory.query.filter_by(
        user_id=session["user_id"]
    ).all()

    return render_template(
        "history.html",
        designs=designs
    )


# View Design
@app.route("/design/<int:id>")
def view_design(id):

    if "user_id" not in session:
        return redirect("/login")

    design = DesignHistory.query.get_or_404(id)

    if design.user_id != session["user_id"]:
        return redirect("/history")

    return render_template(
        "design.html",
        design=design
    )


# Delete Design
@app.route("/delete/<int:id>")
def delete_design(id):

    if "user_id" not in session:
        return redirect("/login")

    design = DesignHistory.query.get_or_404(id)

    if design.user_id != session["user_id"]:
        return redirect("/history")

    db.session.delete(design)

    db.session.commit()

    return redirect("/history")

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

@app.route("/download-report/<int:id>")
def download_report(id):

    if "user_id" not in session:
        return redirect("/login")

    design = DesignHistory.query.get_or_404(id)

    if design.user_id != session["user_id"]:
        return redirect("/history")

    safe_room = design.room_type.replace(" ", "_")
    safe_style = design.style.replace(" ", "_")
    date = design.created_at.strftime("%d-%m-%Y")

    pdf_path = f"{safe_room}_{safe_style}_{date}.pdf"

    doc = SimpleDocTemplate(
        pdf_path,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    story = []

    title_style = ParagraphStyle(
        "Title",
        fontName="Helvetica-Bold",
        fontSize=24,
        alignment=TA_CENTER,
        textColor=HexColor("#0F4C81"),
        spaceAfter=18
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        fontName="Helvetica",
        fontSize=12,
        alignment=TA_CENTER,
        textColor=HexColor("#555555"),
        spaceAfter=20
    )

    heading_style = ParagraphStyle(
        "Heading",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=HexColor("#0F4C81"),
        spaceBefore=16,
        spaceAfter=10
    )

    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=11,
        leading=20,
        spaceAfter=8
    )

    footer_style = ParagraphStyle(
        "Footer",
        fontName="Helvetica-Oblique",
        fontSize=9,
        alignment=TA_CENTER,
        textColor=HexColor("#666666")
    )

    # -----------------------------
    # Title
    # -----------------------------

    story.append(
        Paragraph(
            "🏠 HOMIAI",
            title_style
        )
    )

    story.append(
        Paragraph(
            "AI INTERIOR DESIGN REPORT",
            subtitle_style
        )
    )

    story.append(Spacer(1, 20))

    # -----------------------------
    # Project Details
    # -----------------------------

    details = [
        ["Date", design.created_at.strftime("%d %B %Y")],
        ["Room Type", design.room_type],
        ["Design Style", design.style],
        ["Generated By", session.get("username", "User")]
    ]

    table = Table(details, colWidths=[120, 300])

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF4FC")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ])
    )

    story.append(table)

    story.append(Spacer(1, 25))

    # -----------------------------
    # Uploaded Room Image
    # -----------------------------

    image_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        design.image_name
    )

    if os.path.exists(image_path):

        img = PDFImage(image_path)

        img.drawWidth = 5.8 * inch
        img.drawHeight = 4.2 * inch

        story.append(img)

    story.append(Spacer(1, 25))

    # -----------------------------
    # AI Report Heading
    # -----------------------------

    story.append(
        Paragraph(
            "AI INTERIOR DESIGN REPORT",
            heading_style
        )
    )

    clean_text = re.sub("<.*?>", "", design.suggestions)

    lines = clean_text.split("\n")

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if line.startswith("# "):

            story.append(Spacer(1, 12))

            story.append(
                Paragraph(
                    f"<font color='#0F4C81'><b>{line.replace('# ', '')}</b></font>",
                    heading_style
                )
            )

            continue

        if line.startswith("## "):

            story.append(Spacer(1, 8))

            story.append(
                Paragraph(
                    f"<b>{line.replace('## ', '')}</b>",
                    heading_style
                )
            )

            continue

        if (
            line.startswith("- ")
            or line.startswith("* ")
            or line.startswith("•")
        ):

            bullet = line.replace("- ", "").replace("* ", "").replace("•", "").strip()

            story.append(
                Paragraph(
                    f"&#8226; {bullet}",
                    body_style
                )
            )

            continue

        story.append(
            Paragraph(
                line,
                body_style
            )
        )

    story.append(Spacer(1, 20))

    story.append(
        Paragraph(
            "<hr width='100%'/>",
            body_style
        )
    )

    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "<b>Generated by HomiAI</b>",
            footer_style
        )
    )

    story.append(
        Paragraph(
            "AI Powered Interior Design Assistant",
            footer_style
        )
    )

    story.append(
        Paragraph(
            "Powered by Gemini Vision & Groq AI",
            footer_style
        )
    )

    doc.build(story)

    return send_file(
        pdf_path,
        as_attachment=True
    )
# Create Database
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)