from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    TextAreaField,
    SelectField,
    DateField,
    BooleanField,
    FileField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


class UploadVideoForm(FlaskForm):
    video_file = FileField("Video File", validators=[DataRequired()])
    session_date = DateField("Session Date", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    tags = StringField("Tags (comma-separated)", validators=[Optional(), Length(max=500)])
    visibility = SelectField(
        "Visibility",
        choices=[("private", "Private"), ("shared", "Shared (link)"), ("public", "Public")],
        default="private",
    )
    allow_download = BooleanField("Allow Download")
    submit = SubmitField("Upload")


class EditVideoForm(FlaskForm):
    session_date = DateField("Session Date", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    tags = StringField("Tags (comma-separated)", validators=[Optional(), Length(max=500)])
    visibility = SelectField(
        "Visibility",
        choices=[("private", "Private"), ("shared", "Shared (link)"), ("public", "Public")],
    )
    allow_download = BooleanField("Allow Download")
    submit = SubmitField("Save Changes")


class CreateUserForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(max=255)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters.")],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    role = SelectField("Role", choices=[("user", "User"), ("admin", "Admin")], default="user")
    submit = SubmitField("Create User")
