import json
import os
import webbrowser
from datetime import datetime
from threading import Timer
from flask import Flask, render_template_string, request, redirect, url_for
from tinydb import TinyDB

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "talentvault_nosql.json")

# Initialize NoSQL Document Store (TinyDB)
db = TinyDB(DB_PATH, indent=4)
jobs_col = db.table("jobs_collection")
apps_col = db.table("applications_collection")

# --- FRONTEND TEMPLATES ---

BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TalentVault • NoSQL Recruitment Engine</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f6fb; font-family: 'Segoe UI', system-ui, sans-serif; }
        .navbar-custom { background: linear-gradient(135deg, #1e1b4b, #312e81); }
        .job-card { border: none; border-radius: 12px; transition: transform 0.15s ease; }
        .job-card:hover { transform: translateY(-3px); }
        .json-box { background: #0f172a; color: #38bdf8; border-radius: 10px; padding: 18px; font-family: Consolas, monospace; font-size: 0.9rem; max-height: 450px; overflow-y: auto; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark navbar-custom shadow-sm mb-4">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">⚡ TalentVault <span class="badge bg-info text-dark ms-1">NoSQL Edition</span></a>
            <div class="d-flex gap-2">
                <a href="/" class="btn btn-outline-light btn-sm">Job Board</a>
                <a href="/create-job" class="btn btn-warning btn-sm fw-semibold">+ Post Opening</a>
                <a href="/hr-panel" class="btn btn-light btn-sm fw-semibold">HR Applicants ({{ app_count }})</a>
                <a href="/database" class="btn btn-info btn-sm fw-bold text-dark">{ } Live NoSQL DB</a>
            </div>
        </div>
    </nav>
    <div class="container pb-5">
        {{ content | safe }}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

JOBS_VIEW = """
<div class="d-flex justify-content-between align-items-center mb-4">
    <div>
        <h3 class="fw-bold mb-0">Open Positions</h3>
        <small class="text-muted">Fetched dynamically from NoSQL collection: <code>jobs_collection</code></small>
    </div>
    <span class="badge bg-dark fs-6">{{ jobs|length }} Active Roles</span>
</div>

<div class="row g-4">
    {% for job in jobs %}
    <div class="col-md-6">
        <div class="card job-card shadow-sm h-100 p-2">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start">
                    <h5 class="fw-bold text-indigo mb-1" style="color:#312e81;">{{ job['role'] }}</h5>
                    <span class="badge bg-success-subtle text-success border border-success">{{ job['package'] }}</span>
                </div>
                <p class="text-muted small mb-2">🏢 {{ job['organization'] }} &nbsp;|&nbsp; 📍 {{ job['city'] }} &nbsp;|&nbsp; 🆔 Doc #{{ job.doc_id }}</p>
                <p class="card-text text-secondary">{{ job['summary'] }}</p>
                <div class="mb-2">
                    {% for tag in job['tags'] %}
                    <span class="badge bg-secondary-subtle text-dark me-1">{{ tag }}</span>
                    {% endfor %}
                </div>
            </div>
            <div class="card-footer bg-transparent border-0 pt-0">
                <button class="btn btn-primary w-100 fw-semibold" style="background:#312e81; border:none;" data-bs-toggle="modal" data-bs-target="#applyModal{{ job.doc_id }}">
                    Apply for This Role →
                </button>
            </div>
        </div>
    </div>

    <!-- Application Modal -->
    <div class="modal fade" id="applyModal{{ job.doc_id }}" tabindex="-1">
        <div class="modal-dialog">
            <form action="/submit-application/{{ job.doc_id }}" method="POST" class="modal-content">
                <div class="modal-header text-white" style="background:#312e81;">
                    <h5 class="modal-title">Apply: {{ job['role'] }}</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Candidate Full Name</label>
                        <input type="text" name="candidate_name" class="form-control" placeholder="e.g. Aarav Kulkarni" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Email Address</label>
                        <input type="email" name="email" class="form-control" placeholder="aarav@example.com" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Experience Level</label>
                        <select name="experience" class="form-select">
                            <option value="Fresher / Student">Fresher / Student</option>
                            <option value="1-2 Years">1–2 Years</option>
                            <option value="3+ Years">3+ Years</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Technical Skills & GitHub/Portfolio</label>
                        <textarea name="skills" class="form-control" rows="2" placeholder="Python, Flask, NoSQL, Git..." required></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-success w-100 fw-bold">Save to NoSQL Database</button>
                </div>
            </form>
        </div>
    </div>
    {% endfor %}
</div>
"""

CREATE_JOB_VIEW = """
<div class="mx-auto" style="max-width: 620px;">
    <div class="card shadow-sm border-0 rounded-4 p-4">
        <h4 class="fw-bold mb-1">Publish New Job Document</h4>
        <p class="text-muted small mb-3">Inserts a new JSON document into <code>jobs_collection</code></p>
        <form method="POST">
            <div class="mb-3">
                <label class="form-label fw-semibold">Job Role</label>
                <input type="text" name="role" class="form-control" placeholder="e.g. Backend Python Engineer" required>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label fw-semibold">Company / Organization</label>
                    <input type="text" name="organization" class="form-control" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label fw-semibold">City / Mode</label>
                    <input type="text" name="city" class="form-control" placeholder="Mumbai / Remote" required>
                </div>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label fw-semibold">Compensation</label>
                    <input type="text" name="package" class="form-control" placeholder="₹7,50,000/yr" required>
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label fw-semibold">Skill Tags (comma-separated)</label>
                    <input type="text" name="tags" class="form-control" placeholder="Python, NoSQL, REST API" required>
                </div>
            </div>
            <div class="mb-3">
                <label class="form-label fw-semibold">Role Summary</label>
                <textarea name="summary" class="form-control" rows="3" required></textarea>
            </div>
            <button type="submit" class="btn btn-primary w-100 fw-bold" style="background:#312e81; border:none;">Insert Job Document</button>
        </form>
    </div>
</div>
"""

HR_PANEL_VIEW = """
<div class="d-flex justify-content-between align-items-center mb-3">
    <div>
        <h3 class="fw-bold mb-0">HR Applicant Tracker</h3>
        <small class="text-muted">Live records from <code>applications_collection</code></small>
    </div>
    <a href="/database" class="btn btn-outline-dark btn-sm">Inspect Raw JSON →</a>
</div>

<div class="card shadow-sm border-0 rounded-3 overflow-hidden">
    <table class="table table-hover align-middle mb-0">
        <thead class="table-dark">
            <tr>
                <th>Doc ID</th>
                <th>Candidate</th>
                <th>Applied Role</th>
                <th>Experience</th>
                <th>Skills</th>
                <th>Status</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {% for app in applications %}
            <tr>
                <td><code>#{{ app.doc_id }}</code></td>
                <td>
                    <strong>{{ app['candidate_name'] }}</strong><br>
                    <small class="text-muted">{{ app['email'] }}</small>
                </td>
                <td><span class="badge bg-primary">{{ app['role'] }}</span><br><small>{{ app['organization'] }}</small></td>
                <td>{{ app['experience'] }}</td>
                <td>{{ app['skills'] }}</td>
                <td>
                    {% if app['status'] == 'Shortlisted' %}
                        <span class="badge bg-success">Shortlisted</span>
                    {% else %}
                        <span class="badge bg-warning text-dark">Submitted</span>
                    {% endif %}
                </td>
                <td>
                    <a href="/shortlist/{{ app.doc_id }}" class="btn btn-sm btn-outline-success">Shortlist</a>
                </td>
            </tr>
            {% else %}
            <tr>
                <td colspan="7" class="text-center text-muted py-4">No candidate documents found yet. Apply for a job to test!</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

DATABASE_VIEW = """
<div class="mb-4">
    <h3 class="fw-bold mb-1">Live NoSQL Document Storage (<code>talentvault_nosql.json</code>)</h3>
    <p class="text-muted">Real-time view of the JSON document store saved on disk at: <code>{{ db_path }}</code></p>
</div>

<div class="row g-4">
    <div class="col-md-6">
        <h5 class="fw-bold">1. <code>applications_collection</code> ({{ app_total }} Documents)</h5>
        <pre class="json-box">{{ apps_json }}</pre>
    </div>
    <div class="col-md-6">
        <h5 class="fw-bold">2. <code>jobs_collection</code> ({{ job_total }} Documents)</h5>
        <pre class="json-box">{{ jobs_json }}</pre>
    </div>
</div>
"""

# --- SEED DATA & ROUTES ---

def seed_nosql():
    if len(jobs_col) == 0:
        jobs_col.insert_multiple([
            {
                "role": "AI & Machine Learning Developer",
                "organization": "NeuralPulse Labs",
                "city": "Mumbai / Hybrid",
                "package": "₹9,50,000/yr",
                "tags": ["Python", "OpenCV", "NLP", "PyTorch"],
                "summary": "Develop real-time computer vision and natural language processing pipelines."
            },
            {
                "role": "Full-Stack Flask & NoSQL Engineer",
                "organization": "StackWave Technologies",
                "city": "Bengaluru",
                "package": "₹7,80,000/yr",
                "tags": ["Python", "Flask", "TinyDB", "Bootstrap"],
                "summary": "Build rapid web applications backed by schema-less JSON document stores."
            },
            {
                "role": "Data Science Intern",
                "organization": "QuantMetrics India",
                "city": "Pune / Remote",
                "package": "₹28,000/mo",
                "tags": ["Python", "Pandas", "SQL", "Visualization"],
                "summary": "Clean, model, and visualize large-scale product telemetry datasets."
            },
            {
                "role": "Cloud & NoSQL Database Administrator",
                "organization": "AeroData Systems",
                "city": "Hyderabad",
                "package": "₹8,40,000/yr",
                "tags": ["MongoDB", "JSON", "Indexing", "Security"],
                "summary": "Design high-throughput document collections and automated backup workflows."
            }
        ])

def render_page(template_str, **kwargs):
    inner_html = render_template_string(template_str, **kwargs)
    return render_template_string(BASE_LAYOUT, content=inner_html, app_count=len(apps_col))

@app.route('/')
def index():
    jobs = list(reversed(jobs_col.all()))
    return render_page(JOBS_VIEW, jobs=jobs)

@app.route('/create-job', methods=['GET', 'POST'])
def create_job():
    if request.method == 'POST':
        tag_list = [t.strip() for t in request.form['tags'].split(',') if t.strip()]
        jobs_col.insert({
            "role": request.form['role'],
            "organization": request.form['organization'],
            "city": request.form['city'],
            "package": request.form['package'],
            "tags": tag_list,
            "summary": request.form['summary']
        })
        return redirect(url_for('index'))
    return render_page(CREATE_JOB_VIEW)

@app.route('/submit-application/<int:job_id>', methods=['POST'])
def submit_application(job_id):
    job = jobs_col.get(doc_id=job_id)
    apps_col.insert({
        "job_doc_id": job_id,
        "role": job['role'] if job else f"Job #{job_id}",
        "organization": job['organization'] if job else "Unknown",
        "candidate_name": request.form['candidate_name'],
        "email": request.form['email'],
        "experience": request.form['experience'],
        "skills": request.form['skills'],
        "status": "Submitted",
        "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return redirect(url_for('hr_panel'))

@app.route('/hr-panel')
def hr_panel():
    applications = list(reversed(apps_col.all()))
    return render_page(HR_PANEL_VIEW, applications=applications)

@app.route('/shortlist/<int:app_id>')
def shortlist(app_id):
    apps_col.update({"status": "Shortlisted"}, doc_ids=[app_id])
    return redirect(url_for('hr_panel'))

@app.route('/database')
def database_inspector():
    apps_data = [{**doc, "_doc_id": doc.doc_id} for doc in apps_col.all()]
    jobs_data = [{**doc, "_doc_id": doc.doc_id} for doc in jobs_col.all()]
    return render_page(
        DATABASE_VIEW,
        db_path=DB_PATH,
        app_total=len(apps_data),
        job_total=len(jobs_data),
        apps_json=json.dumps(apps_data, indent=4),
        jobs_json=json.dumps(jobs_data, indent=4)
    )

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000/")

if __name__ == '__main__':
    seed_nosql()
    Timer(1, open_browser).start()
    app.run(port=5000, debug=True, use_reloader=False)