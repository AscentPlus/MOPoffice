# MOP File Tracking System

A Django-based web application for tracking files and managing office procedures following the Manual of Office Procedure (MOP) workflow used in government-style organizations.

## Features

- **Post-based Hierarchy**: Seven-level organizational hierarchy from Secretary to Clerk
- **File Tracking**: Complete file lifecycle management from creation to closure
- **Audit Trail**: Complete history of file movements and actions
- **Document Management**: Support for multiple document types, priorities, and origins
- **User Management**: Controlled user creation by top administrative post only
- **Real-time Updates**: Files appear in recipient's inbox immediately upon forwarding

## Technology Stack

- **Backend**: Django 4.2.28
- **Database**: PostgreSQL
- **Python**: 3.10+

## Database Configuration

The system uses PostgreSQL with the following configuration:
- **Database Name**: MOP_testing
- **User**: postgres
- **Password**: sairam
- **Host**: localhost
- **Port**: 5432

## Installation & Setup

### 0. Create Virtual Environment (Recommended)

It's recommended to use a virtual environment to isolate project dependencies:

**Create virtual environment:**
```bash
python -m venv venv
```

**Activate virtual environment:**

On Windows:
```bash
venv\Scripts\activate
```

On macOS/Linux:
```bash
source venv/bin/activate
```

**Note**: You'll see `(venv)` in your terminal prompt when the virtual environment is active. Always activate the virtual environment before running Django commands or installing packages.

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Database Setup

Ensure PostgreSQL is running and the database `MOP_testing` exists:

```sql
CREATE DATABASE MOP_testing;
```

### 3. Run Migrations

```bash
python manage.py migrate
```

### 4. Populate Initial Data

```bash
python manage.py populate_initial_data
```

This creates:
- 4 Departments (Administration, Finance, HR, IT)
- 7 Posts (Secretary, Joint Secretary, Deputy Secretary, Under Secretary, Section Officer, Assistant, Clerk)
- 9 Document Types (Letter, Memo, Circular, etc.)
- 4 Document Origins (Internal, External, Inter-Department, Public)
- 4 Priority Levels (Urgent, High, Normal, Low)
- 3 Transit Types (Physical, Electronic, Both)
- 7 Document Statuses (Pending, Under Review, Approved, etc.)

### 5. Create Superuser

```bash
python manage.py createsuperuser
```

**Important**: After creating the superuser, you must:
1. Login to admin panel at `http://localhost:8000/admin/`
2. Edit the superuser and assign the **Secretary** post
3. This user will then have full administrative privileges

### 6. Run Development Server

```bash
python manage.py runserver
```

Access the application at `http://localhost:8000/`

## Database Schema

### Master Data Tables

- **department**: Organization departments
- **post**: Official posts with priority-based hierarchy
- **document_type**: Types of documents
- **document_origin**: Origin of documents
- **document_priority**: Priority levels
- **transit_type**: Document transit methods
- **document_status**: Status descriptions

### User Management

- **custom_user**: Extended user model with:
  - Auto-generated user_id (first 2 letters + transaction number)
  - Post assignment
  - Created by tracking
  - Mobile number

### File Tracking

- **file_master**: Main file records with:
  - Auto-generated file_number (FILE/YEAR/XXXXX)
  - Subject, department, document details
  - Current holder and status
  - Closure tracking

- **file_movement**: Transaction log of file movements
  - From/to post tracking
  - Action required flag
  - Timestamp and user tracking

- **file_action**: Actions taken on files
  - Action types: APPROVE, REJECT, RETURN, FORWARD
  - Required remarks
  - Complete audit trail

- **file_document**: Supporting document uploads
  - File attachments
  - Upload tracking

## Post Hierarchy

The system uses numeric priorities to control file movement:

1. **Secretary** (Priority 1) - Top administrative post
2. **Joint Secretary** (Priority 2)
3. **Deputy Secretary** (Priority 3)
4. **Under Secretary** (Priority 4)
5. **Section Officer** (Priority 5)
6. **Assistant** (Priority 6)
7. **Clerk** (Priority 7)

Lower priority number = Higher authority

## Key Workflows

### User Creation
1. Only the top post (Secretary) can create users
2. User ID is auto-generated from username
3. Users are assigned to specific posts
4. Login access controlled by activation status

### File Lifecycle
1. **Creation**: Authorized user creates file with subject and documents
2. **Forwarding**: File forwarded to other posts (action required or view-only)
3. **Action**: Recipient approves, rejects, returns, or forwards
4. **Tracking**: Complete timeline visible to authorized users
5. **Closure**: Final approval/rejection closes the file

### Real-time Updates
- When a file is forwarded, it immediately appears in the recipient's inbox
- All movements are logged with timestamps
- Complete audit trail maintained

## Admin Panel

Access Django admin at `http://localhost:8000/admin/` to:
- Manage master data (departments, posts, document types, etc.)
- Create and manage users
- View file tracking data
- Monitor system activity

## Next Steps

After completing the base setup, the next development phases will include:

1. **Administration Module**: Views for managing master data and users
2. **File Management Module**: File creation, forwarding, and action interfaces
3. **User Interface**: Dashboard, inbox, file detail views
4. **Authentication**: Login system with post-based permissions
5. **Testing**: End-to-end workflow validation

## Project Structure

```
MOP/
├── mop_project/          # Main project settings
├── administration/       # Master data & user management
│   ├── models.py        # Master data models
│   ├── admin.py         # Admin configuration
│   └── management/      # Custom commands
├── filetracking/        # File management & workflow
│   ├── models.py        # File tracking models
│   └── admin.py         # Admin configuration
├── templates/           # Global templates
├── static/              # CSS, JS, images
├── media/               # Uploaded documents
├── requirements.txt     # Python dependencies
└── manage.py           # Django management script
```

## Database Tables Created

All tables have been created with `managed=True`:

✅ department
✅ post
✅ document_type
✅ document_origin
✅ document_priority
✅ transit_type
✅ document_status
✅ custom_user
✅ file_master
✅ file_movement
✅ file_action
✅ file_document

## Support

For issues or questions, refer to the implementation plan and task documentation in the `brain` directory.
