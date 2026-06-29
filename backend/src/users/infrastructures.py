from backend.src.users.repositories import Repository


class Infrastructure(Repository):
    def __init__(self, session):
        super().__init__(session)
