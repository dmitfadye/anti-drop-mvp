import json
from src.db import get_db, reset_init_state_for_tests
from src.sim_security import canonical_phone

# Test the endpoint logic directly
reset_init_state_for_tests()
for db in get_db():
    subject = 'alice'
    old_phone = '+79160000001'
    new_phone = '+79160000002'
    
    # Check current phone
    row = db.execute('SELECT phone FROM users WHERE user_id=?', (subject,)).fetchone()
    current_phone = row["phone"]
    print(f'Before: {current_phone}')
    print(f'Canonical old: {canonical_phone(old_phone)}')
    print(f'Canonical new: {canonical_phone(new_phone)}')
    print(f'Match: {canonical_phone(current_phone) == canonical_phone(old_phone)}')
    
    # Simulate the update
    new_c = canonical_phone(new_phone)
    db.execute(
        'UPDATE users SET phone=?, phone_verified_at=datetime("now") WHERE user_id=?',
        (new_c, subject)
    )
    db.commit()
    
    # Check after
    row = db.execute('SELECT * FROM users WHERE user_id=?', (subject,)).fetchone()
    print(f'After: {dict(row)}')