from app import app as application
# Render will look for 'app' by default, but keep compatibility with 'wsgi:app'
app = application
