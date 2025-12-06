# CCS SBO Management System

A comprehensive web application for managing College of Computer Studies (CCS) Student Body Organization (SBO) student profiles, built with Flask and Supabase.

## Features

### Public Pages
- **Home Page**: Landing page with hero section, features overview, and call-to-action buttons
- **About Page**: Information about SOMS and its mission
- **Team Page**: Showcase of the development team
- **Privacy Policy**: Complete privacy policy documentation
- **Terms of Service**: Terms and conditions for platform usage
- **Responsive Mobile Menu**: Fully functional hamburger menu with smooth interactions on all pages
- **Automatic Academic Year**: Badge automatically updates academic year based on current date (August 1 - July 31)

### Student Management
- **Registration**: Students can register with personal details, academic information, and upload required documents (1x1 picture and signature)
- **Profile Management**: Students can view and update their profiles
- **Document Approval**: Admin review system for uploaded pictures and signatures
- **Email Verification**: Resend verification email modal for unverified accounts

### Administrative Functions
- **Dashboard**: Overview of student statistics and pending approvals
- **Student Management**: Search, filter, edit, and delete student profiles
- **Document Review**: Approve or disapprove student-uploaded pictures and signatures
- **Printing System**: Generate printable student lists organized by program, year, section, and major
- **Archiving**: Archive student groups for historical records
- **Activity Logs**: Track administrative actions and changes

### President Access
- Review student profiles and approval statuses
- Access to administrative functions with appropriate permissions

### Security & Authentication
- Secure login/logout system
- Role-based access control (Student, President, Admin)
- Email verification for new accounts
- Password reset functionality
- Session management
- **Auto-Cleanup**: Supabase cron job automatically deletes unverified accounts after 7 days of inactivity

## Tech Stack

- **Backend**: Python Flask
- **Database**: Supabase (PostgreSQL with real-time capabilities)
- **Authentication**: Supabase Auth
- **File Storage**: Supabase Storage
- **Frontend**: HTML, CSS, JavaScript (Jinja2 templates)
- **Deployment**: Vercel
- **Image Processing**: Pillow

## Prerequisites

- Python 3.8 or higher
- Supabase account and project
- Vercel account (for deployment)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd ccs-sbo-management
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the root directory:
   ```env
   FLASK_SECRET_KEY=your-secret-key-here
   SUPABASE_URL=your-supabase-project-url
   SUPABASE_KEY=your-supabase-anon-key
   SUPABASE_SERVICE_KEY=your-supabase-service-role-key
   ```

5. **Configure Supabase**:
   - Create the necessary tables in your Supabase database
   - Set up storage buckets for `pictures` and `signatures`
   - Configure authentication settings

## Database Schema

### Profiles Table
```sql
CREATE TABLE profiles (
  id UUID REFERENCES auth.users(id) PRIMARY KEY,
  email TEXT,
  student_id TEXT UNIQUE,
  first_name TEXT,
  middle_name TEXT,
  last_name TEXT,
  program TEXT,
  semester TEXT,
  year_level TEXT,
  section TEXT,
  major TEXT,
  picture_url TEXT,
  signature_url TEXT,
  account_type TEXT DEFAULT 'student',
  picture_status TEXT DEFAULT 'pending',
  signature_status TEXT DEFAULT 'pending',
  disapproval_reason TEXT
);
```

### Archived Groups Table
```sql
CREATE TABLE archived_groups (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  academic_year TEXT,
  semester TEXT,
  group_name TEXT,
  student_data JSONB,
  generation_date TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Usage

### Local Development

1. **Run the application**:
   ```bash
   python main.py
   ```

2. **Access the application**:
   Open your browser and navigate to `http://localhost:5000`

### User Roles

- **Students**: Can register, login, view/edit their profile
- **Presidents**: Can review student profiles and access president-specific features
- **Admins**: Full access to all administrative functions

## Deployment

### Vercel Deployment

1. **Connect your repository to Vercel**
2. **Set environment variables in Vercel**:
   - `FLASK_SECRET_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SUPABASE_SERVICE_KEY`
   - `PORT` (automatically set by Vercel)

3. **Deploy**: Vercel will automatically build and deploy using the `vercel.json` configuration

## Project Structure

```
your_project_directory/
│
├── auth/
│   └── routes.py           # Authentication routes (login, register, etc.)
│
├── core/
│   └── routes.py           # Core user routes (profile, settings)
│
├── admin/
│   └── routes.py           # Admin routes (dashboard, student management)
│
├── president/
│   └── routes.py           # President routes (review functions)
│
├── templates/
│   ├── index.html          # Home page with academic year auto-update
│   ├── about.html          # About page with mobile menu
│   ├── privacy.html        # Privacy policy with mobile menu
│   ├── terms.html          # Terms of service with mobile menu
│   ├── team.html           # Team page with mobile menu
│   ├── print_template.html # Printing template
│   │
│   ├── client/             # Student-facing templates
│   │   ├── base.html
│   │   ├── check_email.html
│   │   ├── forgot_password.html
│   │   ├── login.html
│   │   ├── profile.html
│   │   ├── register.html   # With resend verification modal
│   │   └── settings.html
│   │
│   ├── admin/              # Admin templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── students.html
│   │   ├── edit_student.html
│   │   ├── review_student.html
│   │   ├── printing.html
│   │   ├── archive.html
│   │   └── activity_logs.html
│   │
│   └── president/          # President templates
│       ├── base.html
│       ├── dashboard.html
│       └── review_student.html
│
├── static/
│   ├── css/                # Stylesheets
│   │   ├── printing.css
│   │   └── ...
│   │
│   ├── font/               # Custom fonts
│   │   └── ...
│   │
│   └── image/              # Static images
│       ├── background.jpg
│       ├── lspu.png
│       └── Team/           # Team member photos
│
├── .env                    # Environment variables
├── main.py                 # Application entry point
├── config.py               # Configuration settings
├── extensions.py           # Supabase initialization
├── utils.py                # Helper functions and decorators
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel deployment config
├── Project_tree_Directory.txt # Project structure
└── README.md               # This file
```

## Key Features Explained

### Academic Year Auto-Update
The system automatically calculates and displays the current academic year based on the date:
- Academic year runs from **August 1 to July 31**
- Example: December 6, 2025 displays "Academic Year 2025-2026"
- On August 1, 2026, it will automatically update to "Academic Year 2026-2027"
- No manual intervention required

### Mobile Responsiveness
- All pages feature a responsive mobile hamburger menu
- Menu automatically closes when clicking outside or selecting a link
- Smooth transitions and accessible ARIA labels
- Full functionality on devices with screen width below medium breakpoint (md)

### Automated Account Cleanup
- Supabase cron job runs automatically to maintain database hygiene
- Unverified accounts are deleted after 7 days of inactivity
- Users receive reminder to verify their email within the verification period
- Prevents accumulation of unused/spam accounts

## API Endpoints

### Public Routes
- `GET /` - Home page
- `GET /about` - About page
- `GET /team` - Team page
- `GET /privacy` - Privacy policy
- `GET /terms` - Terms of service

### Authentication
- `GET/POST /login` - User login
- `GET/POST /register` - User registration
- `GET /logout` - User logout
- `GET /forgot_password` - Password reset request
- `GET /check_email` - Password reset confirmation
- `POST /auth/resend_verification` - Resend verification email

### Core
- `GET /` - Home page (redirects to profile if logged in)
- `GET /profile` - User profile page
- `GET/POST /settings` - User settings

### Admin
- `GET /admin/dashboard` - Admin dashboard
- `GET /admin/students` - Student management
- `GET/POST /admin/edit_student/<id>` - Edit student profile
- `POST /admin/delete_student/<id>` - Delete student
- `GET /admin/printing` - Printing interface
- `GET /admin/archive` - Archive management
- `GET /admin/review_student/<id>` - Review student documents

### President
- `GET /president/dashboard` - President dashboard
- `GET /president/review_student/<id>` - Review student profiles

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Security Notes

- All uploaded files are validated for size and type
- Signatures must be PNG format with transparent backgrounds
- Role-based access control prevents unauthorized actions
- Sensitive operations require admin privileges
- File uploads are handled securely through Supabase Storage

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support or questions, please contact the development team or create an issue in the repository.
