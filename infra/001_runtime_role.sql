\getenv runtime_password API_DATABASE_PASSWORD
CREATE ROLE antidrop_app LOGIN PASSWORD :'runtime_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE antidrop TO antidrop_app;
GRANT USAGE ON SCHEMA public TO antidrop_app;
