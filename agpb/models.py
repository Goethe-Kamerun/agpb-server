from datetime import datetime
from agpb import db


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True)
    label = db.Column(db.Text)
    created_at = db.Column(db.Date, nullable=False,
                    default=datetime.now().strftime('%Y-%m-%d'))

    def __repr__(self):
        # This is what is shown when object is printed
        return "Category({}, {})".format(
               self.label,
               self.created_at)


class Language(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True)
    label = db.Column(db.String(150), nullable=False)
    lang_code = db.Column(db.String(7))
    country_code = db.Column(db.String(7))
    translation_id = db.Column(db.Integer)

    def __repr__(self):
        # This is what is shown when object is printed
        return "Language({}, {}, {}, {})".format(
               self.label,
               self.lang_code,
               self.country_code,
               self.translation_id)


class Text(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True)
    label = db.Column(db.Text)
    category_id = db.Column(db.Integer)

    def __repr__(self):
        # This is what is shown when object is printed
        return "Text({}, {})".format(
               self.label,
               self.category_id)
