/opt/cockroach-v23.1.1.linux-amd64/cockroach-v23.1.1.linux-amd64/cockroach sql --certs-dir=/var/lib/cockroach/certs/ --host=192.168.1.1:26258

CREATE USER tester WITH PASSWORD 'tester';
GRANT admin TO tester;
