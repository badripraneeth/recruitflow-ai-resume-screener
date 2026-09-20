from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """
    Custom manager for CustomUser where email is the unique identifier for authentication.
    """
    def create_user(self, email, password=None, role='recruiter', **extra_fields):
        if not email:
            raise ValueError('An email address must be provided.')
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        
        # Ensure recruiter role defaults
        if role == 'recruiter':
            extra_fields.setdefault('is_staff', False)
        elif role == 'admin':
            extra_fields.setdefault('is_staff', True)

        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, role='admin', **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model where email is the primary login identifier.
    Roles:
      - recruiter: Default role, handles screening, cannot access Django admin.
      - admin: System administrator, can access Django admin.
    """
    ROLE_RECRUITER = 'recruiter'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_RECRUITER, 'Recruiter'),
        (ROLE_ADMIN, 'Admin'),
    ]

    email = models.EmailField('Email Address', unique=True)
    first_name = models.CharField('First Name', max_length=150, blank=True)
    last_name = models.CharField('Last Name', max_length=150, blank=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_RECRUITER,
        help_text='User permission role (recruiter or admin).'
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False,
        help_text='Designates whether the user can log into the Django admin site. Recruiters are strictly blocked.'
    )
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        full = self.get_full_name()
        return f"{full} ({self.email})" if full else self.email

    def get_full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full if full else self.email

    def get_short_name(self):
        return self.first_name or self.email.split('@')[0]

    @property
    def is_recruiter(self):
        return self.role == self.ROLE_RECRUITER

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    def save(self, *args, **kwargs):
        # Enforce strict separation: recruiters are never staff or superusers
        if self.role == self.ROLE_RECRUITER:
            self.is_staff = False
            self.is_superuser = False
        elif self.role == self.ROLE_ADMIN or self.is_superuser:
            self.role = self.ROLE_ADMIN
            self.is_staff = True
            self.is_superuser = True
        super().save(*args, **kwargs)
