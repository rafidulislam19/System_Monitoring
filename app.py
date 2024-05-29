
import subprocess
from flask import Flask, render_template, request, jsonify
import datetime
import threading
import mysql.connector

app = Flask(__name__)

# Create a MySQL database connection
db = mysql.connector.connect(
    host="localhost",
    user="network_user",
    password="mySQL123!",
    database="network_monitor"
)

# Create a cursor object to interact with the database
cursor = db.cursor()

# Route to handle form submissions and insert data into the database
@app.route('/add_branch', methods=['POST'])
def add_branch():
    if request.method == 'POST':
        try:
            # Get data from the JSON request
            data = request.get_json()
            serial = data.get('serial')
            connection_name = data.get('connection_name')
            ip = data.get('ip')
            vendor = data.get('vendor')
            wan_ip = data.get('wan_ip')

            # Get the current timestamp
            timestamp = get_timestamp()

            # Insert data into the database
            insert_query = f"INSERT INTO network_status (serial, `connection_name`, ip, vendor, `wan_ip`) " \
                           f"VALUES ('{serial}', '{connection_name}', '{ip}', '{vendor}', '{wan_ip}')"
            cursor.execute(insert_query)
            db.commit()

            return jsonify({"message": "Branch added successfully!"})

        except Exception as e:
            return jsonify({"error": str(e)})

# Extract columns from the database table
cursor.execute('SELECT serial, connection_name, ip, vendor, wan_ip FROM network_status')
data = cursor.fetchall()

serials = [row[0] for row in data]
connection_names = [row[1] for row in data]
ips = [row[2] for row in data]
vendors = [row[3] for row in data]
wan_ips = [row[4] for row in data]

connection_statuses = [{'status': 'connected', 'last_change': None, 'downtime': None, 'uptime': None, 'downtime_duration': 0,
                        'count_of_downtime': 0} for _ in wan_ips]

def check_system_status(wan_ip):
    cmd = subprocess.Popen(f'ping {wan_ip}', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, _ = cmd.communicate()
    return wan_ip, "bytes=32" in out.decode('utf-8')

def check_and_update_status(wan_ip, timestamp):
    status = check_system_status(wan_ip)[1]
    
    # Find the index of the current WAN IP
    index = wan_ips.index(wan_ip)
    current_status = connection_statuses[index]

    if current_status['last_change'] is None:
        current_status['last_change'] = timestamp  # Set initial value

    if status and current_status['status'] == 'disconnected':
        downtime_duration = (datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(current_status['last_change'], '%Y-%m-%d %H:%M:%S')).total_seconds()
        current_status['uptime'] = timestamp
        current_status['status'] = 'connected'
        current_status['downtime_duration'] += downtime_duration  # Add to accumulated downtime
        current_status['last_change'] = timestamp
        current_status['count_of_downtime'] += 1  # Increase downtime count
    elif not status and current_status['status'] == 'connected':
        current_status['downtime'] = timestamp
        current_status['status'] = 'disconnected'
        current_status['last_change'] = timestamp

    # Update the connection_statuses list
    connection_statuses[index] = current_status

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_status')
def get_status():
    timestamp = get_timestamp()

    threads = []
    for wan_ip in wan_ips:
        thread = threading.Thread(target=check_and_update_status, args=(wan_ip, timestamp))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    return jsonify(connection_statuses=connection_statuses, serials=serials, connection_names=connection_names,
                   vendors=vendors, wan_ips=wan_ips, ips=ips)

def get_timestamp():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)

