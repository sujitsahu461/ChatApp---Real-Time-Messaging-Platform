# Django Login & Signup Page with MySQL Database

A complete Django web application featuring user authentication with login and signup functionality, integrated with MySQL database and user profile management.

## 📋 Project Overview

This is a Django-based web application that demonstrates:
- **User Registration** - Complete signup form with validation
- **User Authentication** - Secure login system
- **User Profiles** - Profile pictures and user information management
- **Dashboard** - Home page with user-specific content
- **Admin Panel** - Django admin interface for content management

## 🛠️ Tech Stack

- **Backend:** Django 6.0.5
- **Database:** MySQL (SQLite for development)
- **Frontend:** HTML, CSS, JavaScript
- **Python Version:** 3.x

## 📁 Project Structure

```
web/
├── manage.py                 # Django management script
├── db.sqlite3               # SQLite database (development)
├── template/                # HTML templates
│   ├── home.html           # Home page
│   ├── login.html          # Login page
│   └── signup.html         # Signup page
├── media/                   # User-uploaded files
│   └── profile_pics/       # Profile pictures
├── web/                    # Project settings
│   ├── settings.py         # Django settings
│   ├── urls.py             # URL routing
│   ├── asgi.py             # ASGI config
│   └── wsgi.py             # WSGI config
└── webapp/                 # Main application
    ├── models.py           # Database models
    ├── views.py            # View functions
    ├── admin.py            # Admin configuration
    ├── apps.py             # App configuration
    └── migrations/         # Database migrations
```

## 🚀 Getting Started

### Prerequisites
- Python 3.7+
- pip (Python package manager)
- Django 6.0.5

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/sujitsahu461/-Creating-Login-Signup-Page-in-Django-Using-Mysql-Database-Django-Python-Tutorial-with-Mysql.git
   cd "Django Python Tutorial with Mysql"
   ```

2. **Create a virtual environment (optional but recommended)**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or manually install:
   ```bash
   pip install Django==6.0.5
   pip install mysqlclient  # For MySQL support
   ```

4. **Navigate to project directory**
   ```bash
   cd web
   ```

5. **Apply migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser (admin account)**
   ```bash
   python manage.py createsuperuser
   ```
   Follow the prompts to create your admin account.

### Running the Application

1. **Start the development server**
   ```bash
   python manage.py runserver
   ```

2. **Access the application**
   - **Home Page:** http://127.0.0.1:8000/
   - **Login Page:** http://127.0.0.1:8000/login/
   - **Signup Page:** http://127.0.0.1:8000/signup/
   - **Admin Panel:** http://127.0.0.1:8000/admin/

3. **Stop the server**
   - Press `CTRL+BREAK` (Windows) or `CTRL+C` (Mac/Linux)

## 🔐 Features

### Authentication System
- **User Registration:** New users can create accounts with email validation
- **Login:** Secure login with username/password authentication
- **Logout:** Users can securely logout
- **Password Management:** Secure password hashing and validation

### User Profile
- **Profile Picture:** Users can upload and update their profile pictures
- **User Information:** Display user details on dashboard
- **Profile Management:** Edit profile information from admin panel

### Admin Features
- **User Management:** Add, edit, delete users
- **Profile Management:** Manage user profiles
- **Media Management:** Manage uploaded files
- **Content Administration:** Full Django admin interface

## 🗄️ Database Models

### UserProfile Model
```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
```

## 📝 Usage

### Creating a New User
1. Go to the signup page: http://127.0.0.1:8000/signup/
2. Fill in the registration form
3. Submit to create your account
4. Login with your credentials

### Updating Profile Picture
1. Login to your account
2. Go to admin panel: http://127.0.0.1:8000/admin/
3. Navigate to User Profiles
4. Update your profile picture
5. Save changes

## 🔧 Configuration

### Database Configuration
Edit `web/web/settings.py` to use MySQL instead of SQLite:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'your_database_name',
        'USER': 'your_mysql_user',
        'PASSWORD': 'your_mysql_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### Static Files
```bash
python manage.py collectstatic
```

## 📚 Learning Resources

- [Django Official Documentation](https://docs.djangoproject.com/)
- [Django Authentication System](https://docs.djangoproject.com/en/6.0/topics/auth/)
- [Django Models](https://docs.djangoproject.com/en/6.0/topics/db/models/)
- [Django Forms](https://docs.djangoproject.com/en/6.0/topics/forms/)

## 🐛 Troubleshooting

### Static Files Warning
If you see a warning about missing static directory, create it:
```bash
mkdir static
python manage.py collectstatic
```

### Database Issues
```bash
# Reset migrations
python manage.py migrate zero
python manage.py migrate

# Create fresh superuser
python manage.py createsuperuser
```

### Port Already in Use
```bash
python manage.py runserver 8080  # Use different port
```

## 📦 Requirements

See `requirements.txt` for all dependencies.

## 🤝 Contributing

Feel free to fork this repository and submit pull requests for any improvements.

## 📄 License

This project is open source and available under the MIT License.

## 👤 Author

**Sujit Sahu**
- GitHub: [@sujitsahu461](https://github.com/sujitsahu461)

## 📞 Support

For issues, questions, or suggestions, please create an issue on the GitHub repository.

---

**Last Updated:** June 09, 2026
**Django Version:** 6.0.5
**Python Version:** 3.x
