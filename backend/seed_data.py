# -*- coding: utf-8 -*-
"""
Database seeder -- populates Categories and curated problem statements.

Run once after migrations:
    python seed_data.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.idea import Category, Idea

CATEGORIES = [
    {"name": "Web Development", "icon": "\U0001f310", "description": "Full-stack, frontend, and backend web projects"},
    {"name": "AI/ML", "icon": "\U0001f916", "description": "Artificial intelligence and machine learning projects"},
    {"name": "Cybersecurity", "icon": "\U0001f510", "description": "Security, privacy, and threat intelligence"},
    {"name": "IoT", "icon": "\U0001f4e1", "description": "Internet of Things, sensors, and embedded systems"},
    {"name": "Blockchain", "icon": "\u26d3", "description": "Decentralized applications and smart contracts"},
    {"name": "FinTech", "icon": "\U0001f4b3", "description": "Financial technology and payments"},
]

PROBLEMS = [
    {
        "slug": "smart-resume-analyzer",
        "title": "Smart Resume Analyzer",
        "domain": "AI/ML", "difficulty": "Medium",
        "tags": ["NLP", "Hiring"], "popularity_score": 62,
        "short_description": "Rank resumes against a job description.",
        "full_description": "Build a system that analyzes candidate resumes and highlights fit score, missing skills, and role alignment.",
        "relevance": "Companies reduce screening time and improve candidate quality.",
        "problem_statement": "Recruiters spend hours manually screening hundreds of resumes.",
        "tech_stack": ["Python", "Transformers", "Node API", "React"],
        "implementation_steps": ["Collect sample resumes", "Extract skills with NLP", "Train scoring model", "Build recruiter UI"],
        "future_enhancements": ["Bias/fairness reporting", "ATS integrations", "Explainable scoring", "Multi-language resume support"],
    },
    {
        "slug": "phishing-url-detector",
        "title": "Phishing URL Detector",
        "domain": "Cybersecurity", "difficulty": "Hard",
        "tags": ["Security", "Detection"], "popularity_score": 85,
        "short_description": "Detect suspicious links in real time.",
        "full_description": "Design a browser extension or dashboard that flags URLs with likely phishing patterns.",
        "relevance": "Prevents credential theft in enterprises and schools.",
        "problem_statement": "Phishing attacks cost billions annually.",
        "tech_stack": ["JavaScript", "Python", "FastAPI", "Extension APIs"],
        "implementation_steps": ["Gather threat intel", "Feature engineer URL patterns", "Train classifier", "Deploy live scanner"],
        "future_enhancements": ["Organization allowlists", "User report feedback loop", "Realtime IOC enrichment", "Mobile deep-link scanning"],
    },
    {
        "slug": "iot-water-leak-monitor",
        "title": "IoT Water Leak Monitor",
        "domain": "IoT", "difficulty": "Medium",
        "tags": ["Sensors", "Smart Home"], "popularity_score": 58,
        "short_description": "Alert users on abnormal water flow.",
        "full_description": "Use inexpensive sensors and cloud alerts to identify leaks in pipelines and household systems.",
        "relevance": "Saves water, cost, and prevents property damage.",
        "problem_statement": "Undetected water leaks waste millions of gallons and cause expensive property damage.",
        "tech_stack": ["ESP32", "MQTT", "Firebase", "Mobile App"],
        "implementation_steps": ["Connect sensor node", "Stream telemetry", "Set thresholds", "Push mobile alerts"],
        "future_enhancements": ["Predictive maintenance", "Battery optimization", "Multi-sensor fusion", "Auto shutoff valve integration"],
    },
    {
        "slug": "decentralized-certificate-verifier",
        "title": "Decentralized Certificate Verifier",
        "domain": "Blockchain", "difficulty": "Hard",
        "tags": ["Web3", "Education"], "popularity_score": 72,
        "short_description": "Verify credentials without intermediaries.",
        "full_description": "Issue tamper-proof educational certificates and provide instant public verification.",
        "relevance": "Reduces fake certificates and employer verification costs.",
        "problem_statement": "Fraudulent academic credentials undermine trust in education systems globally.",
        "tech_stack": ["Solidity", "Ethers.js", "IPFS", "Node"],
        "implementation_steps": ["Create smart contract", "Design issuer portal", "Store certificate hash", "Build verifier page"],
        "future_enhancements": ["Revocation registry", "Batch issuance", "Privacy-preserving proofs", "Multi-chain support"],
    },
    {
        "slug": "ai-tutor-math",
        "title": "AI Tutor for Math Concepts",
        "domain": "AI/ML", "difficulty": "Easy",
        "tags": ["EdTech", "Chatbot"], "popularity_score": 55,
        "short_description": "Explain math with adaptive hints.",
        "full_description": "Build an assistant that adjusts explanation depth based on learner mistakes and pace.",
        "relevance": "Improves conceptual clarity and self-paced learning.",
        "problem_statement": "Students struggle with math concepts without personalized guidance.",
        "tech_stack": ["JavaScript", "LLM API", "Charts", "LocalStorage"],
        "implementation_steps": ["Define concept graph", "Track learner events", "Generate hints", "Evaluate outcomes"],
        "future_enhancements": ["Spaced repetition", "Teacher dashboards", "Offline mode", "Multi-language tutoring"],
    },
    {
        "slug": "freelancer-trust-score",
        "title": "Freelancer Trust Score",
        "domain": "Web Development", "difficulty": "Medium",
        "tags": ["Marketplace", "Reputation"], "popularity_score": 61,
        "short_description": "Predict delivery reliability and quality.",
        "full_description": "Analyze project history, communication patterns, and client feedback to build trust analytics.",
        "relevance": "Helps clients make better hiring decisions quickly.",
        "problem_statement": "Clients have no reliable way to assess freelancer reliability before hiring.",
        "tech_stack": ["React", "Node", "Chart.js", "Postgres"],
        "implementation_steps": ["Design profile schema", "Aggregate metrics", "Build scoring logic", "Render dashboard"],
        "future_enhancements": ["Explainable metrics", "Anti-gaming detection", "Dispute resolution signals", "Cross-platform imports"],
    },
    {
        "slug": "fraud-aware-payment-gateway",
        "title": "Fraud-Aware Payment Gateway",
        "domain": "FinTech", "difficulty": "Hard",
        "tags": ["Payments", "Risk"], "popularity_score": 90,
        "short_description": "Score transaction fraud risk instantly.",
        "full_description": "Add real-time fraud scoring and explainable transaction decisions in a payment workflow.",
        "relevance": "Reduces chargebacks and merchant losses.",
        "problem_statement": "Online payment fraud costs merchants and consumers billions annually.",
        "tech_stack": ["Kafka", "Python", "Redis", "React"],
        "implementation_steps": ["Capture transaction stream", "Build risk rules", "Train anomaly model", "Create operator console"],
        "future_enhancements": ["Device fingerprinting", "3DS recommendations", "Chargeback workflow", "Model monitoring & drift"],
    },
    {
        "slug": "accessible-ui-auditor",
        "title": "Accessible UI Auto Auditor",
        "domain": "Web Development", "difficulty": "Easy",
        "tags": ["A11y", "Automation"], "popularity_score": 64,
        "short_description": "Find accessibility violations in pages.",
        "full_description": "Build a checker that scans pages and suggests fixes for contrast, labels, and keyboard navigation.",
        "relevance": "Makes products inclusive and regulation-ready.",
        "problem_statement": "Most websites fail basic accessibility standards, excluding millions of users.",
        "tech_stack": ["JavaScript", "Lighthouse", "Node", "CSS"],
        "implementation_steps": ["Run scanner", "Categorize issues", "Show fix snippets", "Track compliance score"],
        "future_enhancements": ["CI integration", "Design system checks", "PDF accessibility checks", "Team issue assignment"],
    },
    {
        "slug": "campus-smart-parking",
        "title": "Campus Smart Parking",
        "domain": "IoT", "difficulty": "Medium",
        "tags": ["Mobility", "Sensors"], "popularity_score": 59,
        "short_description": "Show live parking availability.",
        "full_description": "Use occupancy sensors and route users to nearest available spots in a campus map.",
        "relevance": "Cuts fuel waste and parking frustration.",
        "problem_statement": "Parking congestion on campuses wastes time and fuel for thousands of students daily.",
        "tech_stack": ["LoRa", "Node", "Maps API", "Mobile"],
        "implementation_steps": ["Deploy sensors", "Ingest occupancy", "Compute nearest slots", "Display map routing"],
        "future_enhancements": ["Dynamic pricing", "Reservation system", "EV charging spots", "Anomaly detection on sensors"],
    },
    {
        "slug": "threat-intel-dashboard",
        "title": "Threat Intel Dashboard",
        "domain": "Cybersecurity", "difficulty": "Medium",
        "tags": ["SOC", "Monitoring"], "popularity_score": 70,
        "short_description": "Aggregate indicators from open feeds.",
        "full_description": "Build a dashboard for threat analysts with feed severity filters and IOC enrichment.",
        "relevance": "Speeds response and prioritization in SOC teams.",
        "problem_statement": "Security analysts drown in fragmented threat data from multiple feeds.",
        "tech_stack": ["Python", "Elastic", "React", "REST"],
        "implementation_steps": ["Fetch feeds", "Normalize IOC schema", "Map severity", "Visualize trends"],
        "future_enhancements": ["SOAR hooks", "Entity graphing", "Playbook templates", "Custom scoring rules"],
    },
    {
        "slug": "ai-interview-simulator",
        "title": "AI Interview Simulator",
        "domain": "AI/ML", "difficulty": "Medium",
        "tags": ["Career", "Speech"], "popularity_score": 76,
        "short_description": "Practice interviews with feedback.",
        "full_description": "Generate role-specific interview rounds and evaluate confidence, clarity, and content quality.",
        "relevance": "Improves employability and preparation quality.",
        "problem_statement": "Job seekers lack realistic interview practice with actionable feedback.",
        "tech_stack": ["Web Speech API", "LLM API", "Node", "Charts"],
        "implementation_steps": ["Question bank", "Speech capture", "Feedback rubric", "Progress analytics"],
        "future_enhancements": ["Company-specific rounds", "Answer exemplars", "Rubric personalization", "Mock system design interviews"],
    },
    {
        "slug": "code-review-copilot",
        "title": "Code Review Copilot",
        "domain": "Web Development", "difficulty": "Medium",
        "tags": ["DevEx", "Productivity"], "popularity_score": 83,
        "short_description": "Suggest review comments automatically.",
        "full_description": "Parse pull request diffs and propose quality/security/performance comments.",
        "relevance": "Reduces review fatigue and catches early issues.",
        "problem_statement": "Code reviews are time-consuming and inconsistent across teams.",
        "tech_stack": ["TypeScript", "Git APIs", "LLM API", "Vite"],
        "implementation_steps": ["Parse diff", "Classify issues", "Prioritize findings", "Integrate with UI"],
        "future_enhancements": ["Repo-specific rules", "Auto-fix suggestions", "Policy checks", "Developer coaching mode"],
    },
    {
        "slug": "ai-meeting-minutes-generator",
        "title": "AI Meeting Minutes Generator",
        "domain": "AI/ML", "difficulty": "Easy",
        "tags": ["Productivity", "Summarization"], "popularity_score": 88,
        "short_description": "Summarize meetings into action items.",
        "full_description": "Build a tool that turns meeting notes or transcripts into structured summaries with owners, deadlines, and decisions.",
        "relevance": "Improves execution and reduces communication overhead.",
        "problem_statement": "Teams waste hours writing meeting summaries that often miss key action items.",
        "tech_stack": ["JavaScript", "Text processing", "UI", "LocalStorage"],
        "implementation_steps": ["Input capture", "Chunk & summarize", "Extract tasks", "Export/share"],
        "future_enhancements": ["Calendar integration", "Speaker diarization", "Task sync", "Compliance exports"],
    },
    {
        "slug": "carbon-footprint-tracker",
        "title": "Real-Time Carbon Footprint Tracker",
        "domain": "Web Development", "difficulty": "Easy",
        "tags": ["Sustainability", "Dashboard"], "popularity_score": 60,
        "short_description": "Track carbon impact of daily actions.",
        "full_description": "Build a dashboard that estimates emissions from commuting, energy use, and purchases.",
        "relevance": "Encourages sustainable habits with measurable progress.",
        "problem_statement": "Individuals have no easy way to measure and reduce their carbon footprint.",
        "tech_stack": ["JavaScript", "Charts", "CSS", "LocalStorage"],
        "implementation_steps": ["Define activity inputs", "Estimation formulas", "Visualize trends", "Personalized tips"],
        "future_enhancements": ["CSV import", "Group challenges", "Verified offsets", "Device integrations"],
    },
    {
        "slug": "supply-chain-anomaly-radar",
        "title": "Supply Chain Anomaly Radar",
        "domain": "AI/ML", "difficulty": "Hard",
        "tags": ["Forecasting", "Anomaly"], "popularity_score": 69,
        "short_description": "Detect disruptions in orders and deliveries.",
        "full_description": "Create anomaly detection on lead times, stock levels, and vendor performance with explainable alerts.",
        "relevance": "Prevents stock-outs and improves vendor reliability.",
        "problem_statement": "Supply chain disruptions cause billions in losses due to lack of early detection.",
        "tech_stack": ["Python", "Time-series", "Dashboard", "APIs"],
        "implementation_steps": ["Define KPIs", "Train anomaly model", "Alert policies", "Operator dashboard"],
        "future_enhancements": ["Root-cause graphs", "Vendor scoring", "Scenario simulation", "Auto reorder suggestions"],
    },
]


def seed():
    db = SessionLocal()
    try:
        # Seed categories
        cat_map = {}
        for cat_data in CATEGORIES:
            existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
            if not existing:
                cat = Category(**cat_data)
                db.add(cat)
                db.flush()
                cat_map[cat_data["name"]] = cat.id
            else:
                cat_map[cat_data["name"]] = existing.id

        # Seed ideas
        seeded = 0
        for p in PROBLEMS:
            existing = db.query(Idea).filter(Idea.slug == p["slug"]).first()
            if existing:
                continue
            idea = Idea(
                slug=p["slug"],
                title=p["title"],
                domain=p["domain"],
                difficulty=p["difficulty"],
                category_id=cat_map.get(p["domain"]),
                short_description=p["short_description"],
                full_description=p["full_description"],
                relevance=p.get("relevance"),
                problem_statement=p.get("problem_statement"),
                tags=json.dumps(p.get("tags", [])),
                tech_stack=json.dumps(p.get("tech_stack", [])),
                implementation_steps=json.dumps(p.get("implementation_steps", [])),
                future_enhancements=json.dumps(p.get("future_enhancements", [])),
                popularity_score=p.get("popularity_score", 0),
            )
            db.add(idea)
            seeded += 1

        db.commit()
        print(f"✅ Seeded {seeded} ideas and {len(CATEGORIES)} categories.")
    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
