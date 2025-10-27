# CCS SBO Management System

A comprehensive web application for managing College of Computer Studies (CCS) Student Body Organization (SBO) student profiles, built with Flask and Supabase.

## Features

### Student Management
- **Registration**: Students can register with personal details, academic information, and upload required documents (1x1 picture and signature)
- **Profile Management**: Students can view and update their profiles
- **Document Approval**: Admin review system for uploaded pictures and signatures

### Administrative Functions
- **Dashboard**: Overview of student statistics and pending approvals
- **Student Management**: Search, filter, edit, and delete student profiles
- **Document Review**: Approve or disapprove student-uploaded pictures and signatures
- **Printing System**: Generate printable student lists organized by program, year, section, and major
- **Archiving**: Archive student groups for historical records

### President Access
- Review student profiles and approval statuses
- Access to administrative functions with appropriate permissions

### Security & Authentication
- Secure login/logout system
- Role-based access control (Student, President, Admin)
- Email verification for new accounts
- Password reset functionality
- Session management

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
│   ├── client/            # Student-facing templates
│   ├── admin/             # Admin templates
│   ├── president/         # President templates
│   └── print_template.html # Printing template
│
├── static/
│   ├── css/               # Stylesheets
│   ├── font/              # Custom fonts
│   └── image/             # Static images
│
├── .env                   # Environment variables
├── main.py                # Application entry point
├── config.py              # Configuration settings
├── extensions.py          # Supabase initialization
├── utils.py               # Helper functions and decorators
├── requirements.txt       # Python dependencies
├── vercel.json            # Vercel deployment config
└── README.md              # This file
```

## API Endpoints

### Authentication
- `GET/POST /login` - User login
- `GET/POST /register` - User registration
- `GET /logout` - User logout
- `GET /forgot_password` - Password reset request
- `GET /check_email` - Password reset confirmation

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
