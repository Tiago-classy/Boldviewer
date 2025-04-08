from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id):
        self.id = id

    @staticmethod
    def get(user_id):
        # Replace with a real DB query in the future
        if user_id == "1":
            return User("1")
        return None
