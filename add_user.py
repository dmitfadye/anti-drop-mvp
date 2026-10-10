from src.db import get_db, reset_init_state_for_tests
reset_init_state_for_tests()
for db in get_db():
    db.execute("INSERT OR REPLACE INTO users (user_id, phone, created_at) VALUES ('alice', '+79160000001', datetime('now'))")
    db.commit()
    print('User alice added')
    row = db.execute("SELECT * FROM users WHERE user_id='alice'").fetchone()
    print('User:', dict(row))