import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app import app
import database
import models
import auth

client = TestClient(app)

def test_resume_generation_e2e():
    # 1. Get or create test user
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == "test_resume@example.com").first()
        if not user:
            user = models.User(
                name="Test Resume User",
                email="test_resume@example.com",
                hashed_password=auth.get_password_hash("password123"),
                status="active"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            credits = models.UserCredits(
                user_id=user.id,
                wallet_balance=10.0,
                cost_per_card=0.95,
                sample_resume=True
            )
            db.add(credits)
            db.commit()
        else:
            credits = db.query(models.UserCredits).filter(models.UserCredits.user_id == user.id).first()
            if not credits:
                credits = models.UserCredits(user_id=user.id, wallet_balance=10.0, cost_per_card=0.95, sample_resume=True)
                db.add(credits)
            else:
                credits.wallet_balance = 10.0
                credits.sample_resume = True
            db.commit()

        token = auth.create_access_token({"sub": user.email})
        headers = {"Authorization": f"Bearer {token}"}
        client.cookies.set("access_token", token)

        # 2. Test Generator Page with ?type=resume
        resp_page = client.get("/generator?type=resume", headers=headers)
        assert resp_page.status_code == 200
        assert "AI Smart Resume / CV Maker" in resp_page.text

        # 3. Test Generate Resume API
        payload = {
            "full_name": "Sachin Kumar",
            "job_title": "Computer Operator / Data Entry",
            "mobile": "+91 98765 43210",
            "email": "sachin.kumar@gmail.com",
            "address": "P-171, Gali No. 5, Baljeet Nagar, New Delhi - 110008",
            "career_objective": "To secure a position as a Computer Operator where I can utilize my skills.",
            "qualifications": json.dumps([
                {"degree": "10th", "board": "CBSE Board", "year": "2016", "percentage": "68%"},
                {"degree": "12th", "board": "CBSE Board", "year": "2018", "percentage": "72%"},
                {"degree": "B.Com", "board": "Delhi University", "year": "2021", "percentage": "65%"}
            ]),
            "skills": json.dumps([
                "Basic Knowledge of Computer (MS Office, Word, Excel, PowerPoint & Internet)",
                "Typing Speed: English 35 WPM / Hindi 30 WPM",
                "Tally ERP 9 & Accounting Fundamentals"
            ]),
            "experience_type": "experienced",
            "experience_list": json.dumps([
                {
                    "company": "XYZ Services Pvt. Ltd.",
                    "role": "Computer Operator",
                    "duration": "2 Years (2022 - 2024)",
                    "description": "Handled data management, customer documentation and report preparation."
                }
            ]),
            "father_name": "Sh. Pramod Kumar",
            "dob": "27/08/1999",
            "gender": "Male",
            "marital_status": "Unmarried",
            "languages": "Hindi & English",
            "nationality": "Indian",
            "declaration_place": "New Delhi",
            "declaration_date": "08/11/2026",
            "template_style": "classic"
        }

        resp_gen = client.post("/api/resume/generate", data=payload, headers=headers)
        assert resp_gen.status_code == 200, f"Error: {resp_gen.text}"
        data = resp_gen.json()
        assert data["success"] is True
        run_id = data["run_id"]
        assert "pdf_url" in data
        assert "preview_url" in data
        assert data["pdf_size_kb"] > 0
        assert data["preview_size_kb"] > 0

        # 4. Test PDF download
        resp_pdf = client.get(f"/download-resume/{run_id}/pdf", headers=headers)
        assert resp_pdf.status_code == 200
        assert resp_pdf.headers["content-type"] == "application/pdf"
        assert len(resp_pdf.content) > 1000

        # 5. Test Preview download
        resp_prev = client.get(f"/download-resume/{run_id}/preview", headers=headers)
        assert resp_prev.status_code == 200
        assert resp_prev.headers["content-type"] == "image/png"
        assert len(resp_prev.content) > 1000

        # 6. Test with Photo upload
        from io import BytesIO
        from PIL import Image
        img_buf = BytesIO()
        test_img = Image.new("RGB", (200, 250), color=(50, 100, 200))
        test_img.save(img_buf, format="JPEG")
        img_buf.seek(0)

        files = {"photo": ("test_passport.jpg", img_buf, "image/jpeg")}
        resp_gen_photo = client.post("/api/resume/generate", data=payload, files=files, headers=headers)
        assert resp_gen_photo.status_code == 200
        data_photo = resp_gen_photo.json()
        assert data_photo["success"] is True

        # 7. Test Free Demo Sample Generation (Wallet Balance 0, sample_resume True)
        credits.wallet_balance = 0.0
        credits.sample_resume = True
        db.commit()

        resp_sample = client.post("/api/resume/generate", data=payload, headers=headers)
        assert resp_sample.status_code == 200
        data_sample = resp_sample.json()
        assert data_sample["success"] is True
        assert data_sample["is_sample"] is True

        db.refresh(credits)
        assert credits.sample_resume is False

        # 8. Test Insufficient Balance (Wallet 0, Demo already consumed)
        resp_fail = client.post("/api/resume/generate", data=payload, headers=headers)
        assert resp_fail.status_code == 402

        print("Free Demo Sample & Insufficient Balance Tests Passed!")
    finally:
        db.close()

if __name__ == "__main__":
    test_resume_generation_e2e()
