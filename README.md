# CCS SBO Management System

A complete web application built with Flask and Supabase designed to manage student profiles, handle document approvals, and generate printable class lists for the College of Computer Studies (CCS) Student Body Organization (SBO).

This system provides a three-tiered role-based access model:
* **Student:** Can register, upload their profile picture and signature, and update their information.
* **President:** Can review and approve/disapprove pending student picture and signature submissions.
* **Admin:** Has full control over the system, including student CRUD, manual profile editing, approval management, and class list generation/archiving.

---

## Features

* **Role-Based Access Control:** Separate dashboards and permissions for Students, Presidents, and Admins.
* **Secure Authentication:** Handles user registration, login, logout, and password reset functionality.
* **Profile Management:** Students can upload and update their 1x1 picture and digital signature.
* **File Validation:**
    * Strict file size limits for uploads (defined in `config.py`).
    * Signature validation ensures the file is a valid PNG with a transparent background.
* **Admin Student Dashboard:**
    * Full Create, Read, Update, Delete (CRUD) capabilities for all student profiles.
    * Advanced search and filtering by name, program, year level, section, and major.
* **Approval Workflow:**
    * Admins and Presidents can review pending student submissions (pictures/signatures).
    * Ability to "Approve" or "Disapprove" submissions, including a field for providing a reason for disapproval.
* **Class List Printing:**
    * Filter students by Program, Year, Section, Major, and Semester to form a group.
    * Generates a print-ready HTML preview (`/print_preview`) of the selected group, displaying each student's picture, full name (sorted alphabetically), student ID, and signature.
* **Group Archiving:**
    * Ability to save a snapshot of a generated class list (including all student data and images) to an `archived_groups` table for historical records.
    * Admins can view, preview, and delete these historical archives.

---

## Tech Stack

* **Backend:** **Flask**
    * Uses Blueprints for modular routing (`auth`, `core`, `admin`, `president`).
    * Server-side rendering with **Jinja2** templates.
* **Database:** **Supabase (PostgreSQL)**
    * Manages user profiles, roles, and archived group data.
* **Authentication:** **Supabase Auth**
    * Handles user sign-up, sign-in, and password resets.
* **File Storage:** **Supabase Storage**
    * Stores all student pictures and signatures in separate buckets.
* **Image Processing:** **Pillow**
    * Used server-side to validate signature transparency.
* **Deployment:** **Vercel**
    * Configured for serverless deployment (see `main.py` and `vercel.json`).

---

## Project Structure
/ ├── admin/ │ ├── routes.py # Admin dashboard, student CRUD, printing, archiving ├── auth/ │ ├── routes.py # Login, register, logout, password reset ├── core/ │ ├── routes.py # Core student profile dashboard ├── president/ │ ├── routes.py # President's approval dashboard ├── static/ │ ├── css/ │ └── image/ ├── templates/ │ ├── admin/ # Admin HTML templates │ ├── client/ # Student/Auth HTML templates │ ├── president/ # President HTML templates │ └── print_template.html # Shared template for printing ├── config.py # Configuration loader (e.g., file size limits) ├── extensions.py # Supabase client initialization ├── main.py # Flask app factory (create_app) ├── requirements.txt # Python dependencies ├── utils.py # Helper functions (e.g., auth decorators, transparency check) └── vercel.json # Vercel deployment configuration
