# amtron-exporter
Prometheus Exporter for MENNEKES Amtron 11 C2 Wallbox EV Chargers

![Example Grafana Dashboard](/screenshot.png?raw=true "Example Grafana Dashboard")

### Metrics
By default the metrics will be exposed on port `9877/tcp` at `/`.

```
# HELP env_temperature Environment Temperature
# TYPE env_temperature gauge
env_temperature 33.0
# HELP offered_amperage Offered amperage to the vehicle (as indicated by PWM)
# TYPE offered_amperage gauge
offered_amperage 0.0
# HELP charging_amperage Amperage of all phases while charging
# TYPE charging_amperage gauge
charging_amperage{phase="L1"} 0.0
charging_amperage{phase="L2"} 0.0
charging_amperage{phase="L3"} 0.0
# HELP error_state Whether the charger indicates an error or not
# TYPE error_state gauge
error_state 0.0
# HELP type2_status Type 2 Connector Status
# TYPE type2_status gauge
type2_status 1.0
# HELP load_contactor_cycles Number of type 2 load contactor cycles
# TYPE load_contactor_cycles gauge
load_contactor_cycles 5.0
# HELP type2_plug_cycles Number of type 2 plug cycles
# TYPE type2_plug_cycles gauge
type2_plug_cycles 49.0
# HELP ocpp_voltage OCPP Voltage
# TYPE ocpp_voltage gauge
ocpp_voltage{phase="L1"} 228.0
ocpp_voltage{phase="L2"} 229.0
ocpp_voltage{phase="L3"} 229.0
# HELP ocpp_frequency OCPP Frequency
# TYPE ocpp_frequency gauge
ocpp_frequency 50.0
```

### Usage
This is a hacky script without fancy argument parsing, but for personal
usage it's perfectly fine. You could either start it old-school in a `screen` session,
via process managers like `supervisord` or even write a `systemd` unit for it. 
If you've done anything like that, feel free to PR it to help others to get this exporter up and running.

Configuration is done via environment variables:
```
AMTRON_IP - The IP address of your charger (e.g. 192.168.111.111)
AMTRON_USERNAME - The operator username (default is 'operator')
AMTRON_PASSWORD - The operator password (you can find it in your manual)
```

The exporter can be started like this:
```
cd /path/to/amtron-exporter
python3 -m venv ./venv
source venv/bin/activate
pip install -r requirements.txt
AMTRON_IP=192.168.111.111 AMTRON_USERNAME=operator AMTRON_PASSWORD=operator python3 ./exporter.py
```

Afterwards, you need to configure Prometheus to scrape that target.
An absolute minimal configuration only scraping this exporter looks like this:

```yaml
global:
  scrape_interval: 30s

scrape_configs:
  - job_name: amtron
    static_configs:
      - targets: ['localhost:9877']
```

You then can use the metrics in a visualization tool of your choice, e.g. Grafana.