from django.db import models

# Create your models here.

class Group(models.Model):
    description = models.TextField(default="")
    json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.description}"

class User(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, default="example@gmail.com")
    phone = models.CharField(max_length=16, default="123 458-7895")
    is_active = models.BooleanField(default=True)
    firebase_uid = models.TextField(default="")
    json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    groups = models.ManyToManyField(Group, related_name='users')

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class Profile(models.Model):
    bio = models.TextField(default="")
    json = models.JSONField()
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bio}"
    
class Blitz(models.Model):
    json = models.JSONField()
    location = models.JSONField()
    group_id = models.ForeignKey(Group, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.json}"
    
class Match(models.Model):
    json = models.JSONField()
    blitz_id = models.ForeignKey(Blitz, on_delete=models.CASCADE, related_name='match_group_1')
    blitz_id_2 = models.ForeignKey(Blitz, on_delete=models.CASCADE, related_name='match_group_2')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.json}"
    
class Chat(models.Model):
    json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.json}"
    
class Message(models.Model):
    json = models.JSONField()
    text = models.TextField(default="")
    user_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_message')
    chat_id = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_message')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.json}"
