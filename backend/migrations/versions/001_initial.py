"""Initial immutable PostgreSQL schema, including exclusion-based overlap protection."""

import json
from alembic import op
from sqlalchemy import text

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = [
    "CREATE TABLE business_settings (\n\tid INTEGER NOT NULL, \n\tdata JSON NOT NULL, \n\tPRIMARY KEY (id)\n)",
    "CREATE TABLE portfolio_categories (\n\tid SERIAL NOT NULL, \n\tname JSON NOT NULL, \n\tPRIMARY KEY (id)\n)",
    'CREATE TABLE schedule_rules (\n\tid SERIAL NOT NULL, \n\tweekday INTEGER, \n\tdate VARCHAR(10), \n\tstart VARCHAR(5) NOT NULL, \n\t"end" VARCHAR(5) NOT NULL, \n\tblocked BOOLEAN NOT NULL, \n\tPRIMARY KEY (id)\n)',
    "CREATE TABLE services (\n\tid SERIAL NOT NULL, \n\tname JSON NOT NULL, \n\tdescription JSON NOT NULL, \n\tprice INTEGER NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\tduration INTEGER NOT NULL, \n\timage VARCHAR NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tposition INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tCHECK (duration > 0 AND price >= 0)\n)",
    "CREATE TABLE users (\n\tid BIGINT NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tlanguage VARCHAR(2) NOT NULL, \n\texplicit_language BOOLEAN NOT NULL, \n\tdeletion_requested BOOLEAN NOT NULL, \n\tPRIMARY KEY (id)\n)",
    'CREATE TABLE appointments (\n\tid SERIAL NOT NULL, \n\tuser_id BIGINT NOT NULL, \n\tservice_id INTEGER NOT NULL, \n\tstart TIMESTAMP WITH TIME ZONE NOT NULL, \n\t"end" TIMESTAMP WITH TIME ZONE NOT NULL, \n\tbusy_end TIMESTAMP WITH TIME ZONE NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tsnapshot JSON NOT NULL, \n\tcustomer_confirmed BOOLEAN NOT NULL, \n\tadmin_confirmed BOOLEAN NOT NULL, \n\tverified_by BIGINT, \n\tverified_at TIMESTAMP WITH TIME ZONE, \n\trequest_key VARCHAR(100) NOT NULL, \n\tPRIMARY KEY (id), \n\tCHECK ("end" > start AND busy_end >= "end"), \n\tFOREIGN KEY(user_id) REFERENCES users (id), \n\tFOREIGN KEY(service_id) REFERENCES services (id), \n\tUNIQUE (request_key)\n)',
    "CREATE INDEX ix_appointments_start ON appointments (start)",
    "CREATE INDEX ix_appointments_status ON appointments (status)",
    "CREATE INDEX ix_appointments_user_id ON appointments (user_id)",
    "CREATE TABLE portfolio_items (\n\tid SERIAL NOT NULL, \n\tcategory_id INTEGER, \n\tdescription JSON NOT NULL, \n\timages JSON NOT NULL, \n\tposition INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(category_id) REFERENCES portfolio_categories (id) ON DELETE SET NULL\n)",
    "CREATE TABLE support_conversations (\n\tid SERIAL NOT NULL, \n\tuser_id BIGINT NOT NULL, \n\tstatus VARCHAR NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)",
    "CREATE INDEX ix_support_conversations_user_id ON support_conversations (user_id)",
    "CREATE TABLE appointment_history (\n\tid SERIAL NOT NULL, \n\tappointment_id INTEGER NOT NULL, \n\tactor_id BIGINT NOT NULL, \n\taction VARCHAR(100) NOT NULL, \n\tat TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(appointment_id) REFERENCES appointments (id)\n)",
    "CREATE INDEX ix_appointment_history_appointment_id ON appointment_history (appointment_id)",
    "CREATE TABLE notification_jobs (\n\tid SERIAL NOT NULL, \n\tappointment_id INTEGER, \n\trecipient_id BIGINT NOT NULL, \n\tkind VARCHAR(50) NOT NULL, \n\tpayload JSON NOT NULL, \n\tdue TIMESTAMP WITH TIME ZONE NOT NULL, \n\tstate VARCHAR NOT NULL, \n\tattempts INTEGER NOT NULL, \n\tkey VARCHAR(200) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (key), \n\tFOREIGN KEY(appointment_id) REFERENCES appointments (id), \n\tUNIQUE (key)\n)",
    "CREATE INDEX ix_notification_jobs_state ON notification_jobs (state)",
    "CREATE INDEX ix_notification_jobs_due ON notification_jobs (due)",
    "CREATE TABLE reviews (\n\tid SERIAL NOT NULL, \n\tappointment_id INTEGER NOT NULL, \n\tuser_id BIGINT NOT NULL, \n\trating INTEGER NOT NULL, \n\ttext TEXT NOT NULL, \n\tanonymous BOOLEAN NOT NULL, \n\tvisible BOOLEAN NOT NULL, \n\tat TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tCHECK (rating BETWEEN 1 AND 5), \n\tUNIQUE (appointment_id), \n\tFOREIGN KEY(appointment_id) REFERENCES appointments (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)",
    "CREATE TABLE support_messages (\n\tid SERIAL NOT NULL, \n\tconversation_id INTEGER NOT NULL, \n\tsender_id BIGINT NOT NULL, \n\ttext TEXT NOT NULL, \n\timage VARCHAR NOT NULL, \n\tat TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(conversation_id) REFERENCES support_conversations (id), \n\tFOREIGN KEY(sender_id) REFERENCES users (id)\n)",
    "CREATE INDEX ix_support_messages_conversation_id ON support_messages (conversation_id)",
]
INITIAL = {
    "name": {"ru": "Запись онлайн", "en": "Online booking"},
    "description": {"ru": "", "en": ""},
    "timezone": "Europe/Moscow",
    "currency": "RUB",
    "accent": "#5367db",
    "address": "",
    "phone": "",
    "telegram": "",
    "website": "",
    "social_links": [],
    "logo": "",
    "cover": "",
    "horizon_days": 60,
    "notice_minutes": 60,
    "cancel_minutes": 120,
    "slot_minutes": 30,
    "buffer_minutes": 0,
    "reminder_hours": 24,
}


def upgrade():
    for statement in SCHEMA:
        op.execute(statement)
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("""ALTER TABLE appointments ADD CONSTRAINT appointments_no_overlap
        EXCLUDE USING gist (tstzrange(start, busy_end, '[)') WITH &&)
        WHERE (status = 'booked')""")
    op.get_bind().execute(
        text("INSERT INTO business_settings (id, data) VALUES (1, CAST(:data AS json))"), {"data": json.dumps(INITIAL)}
    )


def downgrade():
    op.drop_table("support_messages")
    op.drop_table("reviews")
    op.drop_table("notification_jobs")
    op.drop_table("appointment_history")
    op.drop_table("support_conversations")
    op.drop_table("portfolio_items")
    op.drop_table("appointments")
    op.drop_table("users")
    op.drop_table("services")
    op.drop_table("schedule_rules")
    op.drop_table("portfolio_categories")
    op.drop_table("business_settings")
