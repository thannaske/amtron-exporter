# amtron-exporter
Prometheus Exporter for MENNEKES Amtron 11 C2 Wallbox EV Chargers

This repository is currently under development and not feature-complete, yet.

### Metrics
By default the metrics will be exposed on port 9877 on `/`.

```
# HELP env_temperature Environment Temperature
# TYPE env_temperature gauge
env_temperature 40.0
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
type2_status{type2_status="A"} 1.0
type2_status{type2_status="B"} 0.0
type2_status{type2_status="C"} 0.0
type2_status{type2_status="D"} 0.0
type2_status{type2_status="E"} 0.0
type2_status{type2_status="F"} 0.0
# HELP load_contactor_cycles Number of type 2 load contactor cycles
# TYPE load_contactor_cycles gauge
load_contactor_cycles 5.0
# HELP type2_plug_cycles Number of type 2 plug cycles
# TYPE type2_plug_cycles gauge
type2_plug_cycles 49.0
```
