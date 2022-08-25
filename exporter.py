import hashlib
import logging
import os
import re
import time
import requests
from prometheus_client import start_http_server, Gauge, Enum


class AmtronMetrics:
    def __init__(self, ip_address, username, password, polling_interval_seconds=5):
        self.ip_address = ip_address
        self.username = username
        self.password = password

        self.polling_interval_seconds = polling_interval_seconds

        # Prometheus metrics to collect
        self.env_temperature = Gauge("env_temperature", "Environment Temperature")
        self.offered_amperage = Gauge("offered_amperage", "Offered amperage to the vehicle (as indicated by PWM)")
        self.charging_amperage = Gauge("charging_amperage", "Amperage of all phases while charging", ["phase"])
        self.error_state = Gauge("error_state", "Whether the charger indicates an error or not")
        self.type2_status = Gauge("type2_status", "Type 2 Connector Status")
        self.load_contactor_cycles = Gauge("load_contactor_cycles", "Number of type 2 load contactor cycles")
        self.type2_plug_cycles = Gauge("type2_plug_cycles", "Number of type 2 plug cycles")
        self.ocpp_voltage = Gauge("ocpp_voltage", "OCPP Voltage", ["phase"])
        self.ocpp_frequency = Gauge("ocpp_frequency", "OCPP Frequency")

        # Authentication
        self.session_id = None

    def run_metrics_loop(self):
        """Metrics fetching loop"""

        while True:
            logging.info("Starting to fetch information from Amtron web interface.")
            self.fetch()
            logging.info("Finished fetching information from Amtron web interface. Sleeping ...")

            time.sleep(self.polling_interval_seconds)

    def fetch(self):
        """
        Get metrics from Amtron web interface and refresh Prometheus metrics with new values.
        """
        if not self.session_id:
            self.login()

        successfully_fetched = False
        fetch_data = None

        while not successfully_fetched:
            fetch_request = requests.get(url=f"http://{self.ip_address}:80/json/dashboard.json", headers={
                "Authorization": self.session_id,
            })

            if fetch_request.status_code != 200:
                print(f"ERROR: Amtron web interface unexpectedly responded with HTTP {fetch_request.status_code}.")
                return False

            fetch_data = fetch_request.json()

            if "logged_in" in fetch_data:
                if not fetch_data["logged_in"]:
                    # Our session ID expired, we need to re-authenticate and try again
                    self.login()
                    continue

            successfully_fetched = True

        if fetch_data is not None:
            parser = AmtronParser(fetch_data)

            # Gauges and histograms without labels
            self.env_temperature.set(parser.env_temperature())
            self.offered_amperage.set(parser.offered_amperage())
            self.type2_status.set(parser.type2_status())
            self.error_state.set(parser.error_state())
            self.load_contactor_cycles.set(parser.load_contactor_cycles())
            self.type2_plug_cycles.set(parser.type2_plug_cycles())
            self.ocpp_frequency.set(parser.ocpp_frequency())

            # Charging Amperage (with labels)
            charging_amperage = parser.charging_amperage()
            self.charging_amperage.labels(phase="L1").set(charging_amperage["L1"])
            self.charging_amperage.labels(phase="L2").set(charging_amperage["L2"])
            self.charging_amperage.labels(phase="L3").set(charging_amperage["L3"])

            # OCPP Voltage (with labels)
            ocpp_voltage = parser.ocpp_voltage()
            self.ocpp_voltage.labels(phase="L1").set(ocpp_voltage["L1"])
            self.ocpp_voltage.labels(phase="L2").set(ocpp_voltage["L2"])
            self.ocpp_voltage.labels(phase="L3").set(ocpp_voltage["L3"])


    def login(self) -> bool:
        token_request = requests.get(url=f"http://{self.ip_address}:80/json/login")
        token_data = token_request.json()

        # Create the SH256 has from password and token
        password_hash = hashlib.sha256(self.password.encode("utf-8") + token_data["token"].encode("utf-8")).hexdigest()

        auth_request = requests.post(url=f"http://{self.ip_address}:80/json/login", json={
            "username": self.username,
            "password": password_hash,
        })

        auth_data = auth_request.json()

        if auth_data["logged_in"] is True and auth_data["change_default_pw"] is False and auth_data["set_master_rfid"] is False:
            # We only can proceed scraping the metrics if the user
            # is logged in and doesn't need to interact with the charger.
            self.session_id = auth_data['session']['id']
            return True

        if auth_data["change_default_pw"] is True or auth_data["set_master_rfid"] is True:
            print("ERROR: The charger needs to be configured before scraping metrics.")
        else:
            print("ERROR: Unable to sign in to Amtron web interface. Please check username and password.")

        self.session_id = None
        return False


class AmtronParser:
    def __init__(self, data):
        self.data = data

    def env_temperature(self) -> float:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "emanager_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "EnergyManagerTable_energyman":
                            for value in field["value"]["items"]:
                                if "key" in value and value["key"] == "StateMon_energyman":
                                    regex = r"^.*(\+|-)(?P<value>\d+\.\d+)(\sC).*$"
                                    match = re.match(regex, value["c2"])

                                    if match:
                                        return float(match.group("value"))
                                    else:
                                        return -99.0
        except Exception as e:
            print(f"ERROR: Unable to parse environment temperature. Exception: {str(e)}")

        return -99.0

    def type2_status(self) -> float:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "system_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "Type2StateConnector1_vehicleif":
                            regex = r"^\((?P<value>\w{1})\).*$"
                            match = re.match(regex, field["value"])

                            if match:
                                status = str(match.group("value"))
                                if status == "A":
                                    return 1.0
                                elif status == "B":
                                    return 2.0
                                elif status == "C":
                                    return 3.0
                                elif status == "D":
                                    return 4.0
                                elif status == "E":
                                    return 5.0
                                elif status == "F":
                                    return 6.0

                            else:
                                return -1.0
        except Exception as e:
            print(f"ERROR: Unable to parse type 2 status. Exception: {str(e)}")

        return -1.0

    def offered_amperage(self) -> float:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "system_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "SignaledCurrentLimit_vehicleif":
                            regex = r"^(?P<value>\d+\.?\d*)\sA$"
                            match = re.match(regex, field["value"])

                            if match:
                                return float(match.group("value"))
                            else:
                                return -99.0
        except Exception as e:
            print(f"ERROR: Unable to parse offered amperage. Exception: {str(e)}")

        return -99.0

    def charging_amperage(self) -> dict:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "system_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "OcppMeterCurrent_meter":
                            regex = r"^\(\s(?P<L1>\d+\.\d+)\s\|\s(?P<L2>\d+\.\d+)\s\|\s(?P<L3>\d+\.\d+)\s\)\s\[A\]$"
                            match = re.match(regex, field["value"])

                            if match:
                                return {
                                    "L1": float(match.group("L1")),
                                    "L2": float(match.group("L2")),
                                    "L3": float(match.group("L3")),
                                }
                            else:
                                return {
                                    "L1": -99.0,
                                    "L2": -99.0,
                                    "L3": -99.0,
                                }
        except Exception as e:
            print(f"ERROR: Unable to parse charging amperage. Exception: {str(e)}")

        return {
            "L1": -99.0,
            "L2": -99.0,
            "L3": -99.0,
        }

    def ocpp_voltage(self) -> dict:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "emanager_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "FirstMeterTable_meter":
                            for subfield in field["value"]["items"]:
                                if "key" in subfield and subfield["key"] == "OcppMeterVoltage_meter":
                                    regex = r"^\(\s(?P<L1>\d+)\s\|\s(?P<L2>\d+)\s\|\s(?P<L3>\d+)\s\)\s\[V\]$"
                                    match = re.match(regex, subfield["c2"])

                                    if match:
                                        return {
                                            "L1": float(match.group("L1")),
                                            "L2": float(match.group("L2")),
                                            "L3": float(match.group("L3")),
                                        }
                                    else:
                                        return {
                                            "L1": -1.0,
                                            "L2": -1.0,
                                            "L3": -1.0,
                                        }
        except Exception as e:
            print(f"ERROR: Unable to parse OCPP voltage. Exception: {str(e)}")

        return {
            "L1": -1.0,
            "L2": -1.0,
            "L3": -1.0,
        }

    def ocpp_frequency(self) -> float:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "emanager_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "FirstMeterTable_meter":
                            for subfield in field["value"]["items"]:
                                if "key" in subfield and subfield["key"] == "OcppMeterFrequency_meter":
                                    regex = r"^(?P<value>\d+\.\d+)\sHz$"
                                    match = re.match(regex, subfield["c2"])

                                    if match:
                                        return match.group("value")
                                    else:
                                        return -1.0
        except Exception as e:
            print(f"ERROR: Unable to parse OCPP frequency. Exception: {str(e)}")

        return -1.0

    def error_state(self) -> int:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "system_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "ErrorsList_custom":
                            if field["value"] == "No errors":
                                return 0
                            else:
                                return 1
        except Exception as e:
            print(f"ERROR: Unable to parse errors. Exception: {str(e)}")

        return -99

    def load_contactor_cycles(self) -> int:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "system_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "Type2NumberContactorCyclesRO_vehicleif":
                            regex = r"^(?P<value>\d+)/.*$"
                            match = re.match(regex, field["value"])

                            if match:
                                return int(match.group("value"))
                            else:
                                return -99
        except Exception as e:
            print(f"ERROR: Unable to parse load contactor cycles. Exception: {str(e)}")

        return -99

    def type2_plug_cycles(self) -> int:
        try:
            for group in self.data["groups"]:
                if "key" in group and group["key"] == "system_status":
                    for field in group["fields"]:
                        if "key" in field and field["key"] == "Type2PlugCounterRO_vehicleif":
                            regex = r"^(?P<value>\d+)/.*$"
                            match = re.match(regex, field["value"])

                            if match:
                                return int(match.group("value"))
                            else:
                                return -99
        except Exception as e:
            print(f"ERROR: Unable to parse type 2 plug cycles. Exception: {str(e)}")

        return -99


def main():
    """Main entry point"""
    ip_address = str(os.getenv("AMTRON_IP", "127.0.0.1"))
    username = str(os.getenv("AMTRON_USERNAME", "operator"))
    password = str(os.getenv("AMTRON_PASSWORD", "password"))

    polling_interval_seconds = int(os.getenv("POLLING_INTERVAL_SECONDS", "60"))
    exporter_port = int(os.getenv("EXPORTER_PORT", "9877"))

    app_metrics = AmtronMetrics(
        ip_address=ip_address,
        username=username,
        password=password,
        polling_interval_seconds=polling_interval_seconds
    )
    start_http_server(exporter_port)
    app_metrics.run_metrics_loop()


if __name__ == "__main__":
    main()
