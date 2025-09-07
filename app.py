import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from collections import defaultdict
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

VERDI_API_KEY = os.environ.get("VERDI_API_KEY")


def getData(start_date, end_date, filter_by):
    apiURL = f"https://tryverdi.com/api/transaction_data?user_id={filter_by}&start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {VERDI_API_KEY}"}
    response = requests.get(url=apiURL, headers=headers)
    response.raise_for_status()  # raises HTTPError if request failed
    return response.json()


def reports_3pl(data):
    def count_orders(data):
        return len(data)

    def total_fare(data):
        return round(sum(abs(float(order["amount"])) for order in data), 2)

    def average_fare(data):
        num_orders = count_orders(data)
        return round(total_fare(data) / num_orders, 2) if num_orders > 0 else 0

    def average_time_taken(data):
        total_minutes = 0
        count = 0
        for order in data:
            created_str = order.get("created_at")
            successful_str = order.get("delivery_task", {}).get("successful_at")
            if not created_str or not successful_str:
                continue
            try:
                created = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
                successful = datetime.strptime(successful_str, "%Y-%m-%d %H:%M:%S")
                total_minutes += (successful - created).total_seconds() / 60
                count += 1
            except:
                continue
        return round(total_minutes / count, 2) if count > 0 else 0

    def total_earnings(data):
        return round(total_fare(data) * 0.85, 2)

    def total_revenue(data):
        fare = total_fare(data)
        return round(fare - (fare * 0.85), 2)

    def charts_per_driver_group(data):
        groups = defaultdict(list)
        for order in data:
            driver_name = order.get("pickup_task", {}).get("driver_name", "")
            if not driver_name:
                continue
            group = driver_name.split()[-1].upper()
            groups[group].append(order)

        result = {
            "number_of_orders": {},
            "total_fare": {},
            "average_fare": {},
            "total_earnings": {},
        }

        for group, orders in groups.items():
            num_orders = len(orders)
            fare = round(sum(abs(float(o["amount"])) for o in orders), 2)
            avg_fare = round(fare / num_orders, 2) if num_orders > 0 else 0
            earnings = round(fare * 0.85, 2)

            result["number_of_orders"][group] = num_orders
            result["total_fare"][group] = fare
            result["average_fare"][group] = avg_fare
            result["total_earnings"][group] = earnings

        return result

    def table_data_rows(data):
        drivers = defaultdict(
            lambda: {
                "Amount": 0,
                "Orders": 0,
                "DeliveryTimes": [],
                "AssignTimes": [],
                "PickupWaits": [],
                "TravelTimes": [],
                "DropoffWaits": [],
            }
        )

        def parse_dt(ts):
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") if ts else None

        for order in data:
            driver = order.get("pickup_task", {}).get("driver_name", "Unknown")
            amount_str = order.get("amount")

            # Parse amount
            try:
                amount = round(abs(float(amount_str)), 2)
            except:
                amount = 0

            # Parse timestamps
            created = parse_dt(order.get("created_at"))
            pickup = order.get("pickup_task", {})
            delivery = order.get("delivery_task", {})

            pickup_assigned = parse_dt(pickup.get("assigned_at"))
            pickup_arrived = parse_dt(pickup.get("arrived_at"))
            pickup_success = parse_dt(pickup.get("successful_at"))

            delivery_started = parse_dt(delivery.get("started_at"))
            delivery_arrived = parse_dt(delivery.get("arrived_at"))
            delivery_success = parse_dt(delivery.get("successful_at"))

            # Delivery time
            if created and delivery_success:
                drivers[driver]["DeliveryTimes"].append(
                    (delivery_success - created).total_seconds() / 60
                )

            # Time to assign
            if created and pickup_assigned:
                drivers[driver]["AssignTimes"].append(
                    (pickup_assigned - created).total_seconds() / 60
                )

            # Pickup waiting
            if pickup_success and pickup_arrived:
                drivers[driver]["PickupWaits"].append(
                    (pickup_success - pickup_arrived).total_seconds() / 60
                )

            # Travel to customer
            if delivery_arrived and delivery_started:
                drivers[driver]["TravelTimes"].append(
                    (delivery_arrived - delivery_started).total_seconds() / 60
                )

            # Dropoff waiting
            if delivery_success and delivery_arrived:
                drivers[driver]["DropoffWaits"].append(
                    (delivery_success - delivery_arrived).total_seconds() / 60
                )

            # Update earnings
            drivers[driver]["Amount"] += amount
            drivers[driver]["Orders"] += 1

        # Build final rows
        rows = []
        for driver, stats in drivers.items():

            def avg(lst):
                return round(sum(lst) / len(lst), 2) if lst else None

            rows.append(
                {
                    "Driver": driver,
                    "Orders": stats["Orders"],
                    "Amount": round(stats["Amount"], 2),
                    "Average Delivery Time (min)": avg(stats["DeliveryTimes"]),
                    "Avg Time to Assign (min)": avg(stats["AssignTimes"]),
                    "Avg Pickup Waiting (min)": avg(stats["PickupWaits"]),
                    "Avg Travel to Customer (min)": avg(stats["TravelTimes"]),
                    "Avg Dropoff Waiting (min)": avg(stats["DropoffWaits"]),
                }
            )

        return rows

    # ---- Build the summary ----
    summary = {
        "Number of Orders": count_orders(data),
        "Total Fare": total_fare(data),
        "Average Fare": average_fare(data),
        "Average Time Taken (minutes)": average_time_taken(data),
        "Total Earnings": total_earnings(data),
        "Total Revenue": total_revenue(data),
        "Charts": charts_per_driver_group(data),
        "table_data": table_data_rows(data),
    }

    return summary


def reports_client(data, start_dt, end_dt):
    def count_orders(data):
        return len(data)

    def total_fare(data):
        return round(sum(abs(float(order["amount"])) for order in data), 2)

    def average_fare(data):
        num_orders = count_orders(data)
        return round(total_fare(data) / num_orders, 2) if num_orders > 0 else 0

    def average_time_taken(data):
        total_minutes = 0
        count = 0
        for order in data:
            created_str = order.get("created_at")
            successful_str = order.get("delivery_task", {}).get("successful_at")
            if not created_str or not successful_str:
                continue
            try:
                created = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
                successful = datetime.strptime(successful_str, "%Y-%m-%d %H:%M:%S")
                total_minutes += (successful - created).total_seconds() / 60
                count += 1
            except:
                continue
        return round(total_minutes / count, 2) if count > 0 else 0

    def charts_per_time_slot(data, start_time, end_time):
        # Build unique hourly buckets based on the time range (not date range)
        buckets = []
        seen_buckets = set()

        # Create a dummy date to work with time ranges
        dummy_date = datetime(2024, 1, 1)
        current_time = datetime.combine(dummy_date.date(), start_time)
        end_datetime = datetime.combine(dummy_date.date(), end_time)

        # Handle overnight time ranges (e.g., 22:00 to 05:00)
        if end_time < start_time:
            end_datetime += timedelta(days=1)

        while current_time < end_datetime:
            next_hour = current_time + timedelta(hours=1)
            bucket_name = f"{current_time.hour}-{next_hour.hour % 24}"

            if bucket_name not in seen_buckets:
                buckets.append(bucket_name)
                seen_buckets.add(bucket_name)

            current_time = next_hour

        # Count orders into buckets
        bucket_counts = {b: 0 for b in buckets}
        for order in data:
            created_str = order.get("created_at")
            if not created_str:
                continue
            try:
                created = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
                order_bucket = f"{created.hour}-{(created.hour + 1) % 24}"
                if order_bucket in bucket_counts:
                    bucket_counts[order_bucket] += 1
            except:
                continue

        # ✅ Sort the buckets by starting hour
        sorted_buckets = sorted(
            bucket_counts.keys(), key=lambda x: int(x.split("-")[0])
        )
        sorted_bucket_counts = {b: bucket_counts[b] for b in sorted_buckets}

        # Split into 2 charts if number of buckets > 10
        if len(sorted_buckets) > 10:
            mid = len(sorted_buckets) // 2
            return {
                f"{sorted_buckets[0]} to {sorted_buckets[mid-1]}": {
                    b: sorted_bucket_counts[b] for b in sorted_buckets[:mid]
                },
                f"{sorted_buckets[mid]} to {sorted_buckets[-1]}": {
                    b: sorted_bucket_counts[b] for b in sorted_buckets[mid:]
                },
            }
        else:
            return {
                f"{sorted_buckets[0]} to {sorted_buckets[-1]}": sorted_bucket_counts
            }

    def table_data_rows(data):
        clients = defaultdict(
            lambda: {
                "Amount": 0,
                "Orders": 0,
                "DeliveryTimes": [],
                "AssignTimes": [],
                "PickupWaits": [],
                "TravelTimes": [],
                "DropoffWaits": [],
            }
        )

        def parse_dt(ts):
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") if ts else None

        for order in data:
            client = order.get("user_name", "Unknown")
            amount_str = order.get("amount")

            # Parse amount
            try:
                amount = round(abs(float(amount_str)), 2)
            except:
                amount = 0

            # Parse timestamps
            created = parse_dt(order.get("created_at"))
            pickup = order.get("pickup_task", {})
            delivery = order.get("delivery_task", {})

            pickup_assigned = parse_dt(pickup.get("assigned_at"))
            pickup_arrived = parse_dt(pickup.get("arrived_at"))
            pickup_success = parse_dt(pickup.get("successful_at"))

            delivery_started = parse_dt(delivery.get("started_at"))
            delivery_arrived = parse_dt(delivery.get("arrived_at"))
            delivery_success = parse_dt(delivery.get("successful_at"))

            # Delivery time (created → delivery success)
            if created and delivery_success:
                clients[client]["DeliveryTimes"].append(
                    (delivery_success - created).total_seconds() / 60
                )

            # Time to assign
            if created and pickup_assigned:
                clients[client]["AssignTimes"].append(
                    (pickup_assigned - created).total_seconds() / 60
                )

            # Pickup waiting
            if pickup_success and pickup_arrived:
                clients[client]["PickupWaits"].append(
                    (pickup_success - pickup_arrived).total_seconds() / 60
                )

            # Travel to customer
            if delivery_arrived and delivery_started:
                clients[client]["TravelTimes"].append(
                    (delivery_arrived - delivery_started).total_seconds() / 60
                )

            # Dropoff waiting
            if delivery_success and delivery_arrived:
                clients[client]["DropoffWaits"].append(
                    (delivery_success - delivery_arrived).total_seconds() / 60
                )

            # Update fare & orders
            clients[client]["Amount"] += amount
            clients[client]["Orders"] += 1

        # ---- Build final rows ----
        rows = []
        for client, stats in clients.items():

            def avg(lst):
                return round(sum(lst) / len(lst), 2) if lst else None

            avg_time = avg(stats["DeliveryTimes"])
            avg_assign = avg(stats["AssignTimes"])
            avg_pickup_wait = avg(stats["PickupWaits"])
            avg_travel = avg(stats["TravelTimes"])
            avg_dropoff_wait = avg(stats["DropoffWaits"])

            avg_fare = (
                round(stats["Amount"] / stats["Orders"], 2)
                if stats["Orders"] > 0
                else 0
            )

            rows.append(
                {
                    "Client": client,
                    "Orders": stats["Orders"],
                    "Total Fare": round(stats["Amount"], 2),
                    "Average Fare": avg_fare,
                    "Average Delivery Time (min)": avg_time,
                    "Avg Time to Assign (min)": avg_assign,
                    "Avg Pickup Waiting (min)": avg_pickup_wait,
                    "Avg Travel to Customer (min)": avg_travel,
                    "Avg Dropoff Waiting (min)": avg_dropoff_wait,
                }
            )

        return rows

    # Extract just the time components for chart creation
    start_time = start_dt.time()
    end_time = end_dt.time()

    # ---- Build the summary ----
    summary = {
        "number_of_orders": count_orders(data),
        "total_fare": total_fare(data),
        "average_fare": average_fare(data),
        "average_delivery_time": average_time_taken(data),
        "charts": charts_per_time_slot(data, start_time, end_time),
        "table": table_data_rows(data),
    }

    return summary


@app.route("/client_report", methods=["GET"])
def generate_client_report():
    # Read query parameters
    start_date = request.args.get("start_date")  # e.g. "2025-01-01"
    end_date = request.args.get("end_date")  # e.g. "2025-01-02"
    filter_by = request.args.getlist("filter_by")  # e.g. ["Admin", "V Thru"] or ["all"]
    status = request.args.get("status", "all")  # e.g. "success" or "all"
    start_time = request.args.get("start_time", "00:00")
    end_time = request.args.get("end_time", "23:59")

    # Parse dates
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
    end_time_obj = datetime.strptime(end_time, "%H:%M").time()

    # Fetch base data for the entire date range
    data = getData(start_date, end_date, "all")

    # ✅ NEW: Filter by daily time ranges
    def is_within_daily_time_range(order_datetime, start_time, end_time):
        """Check if order time falls within the daily time range."""
        order_time = order_datetime.time()

        # Handle overnight time ranges (e.g., 22:00 to 05:00)
        if end_time < start_time:
            # Overnight: order should be after start_time OR before end_time
            return order_time >= start_time or order_time <= end_time
        else:
            # Same day: order should be between start_time and end_time
            return start_time <= order_time <= end_time

    # ✅ Filter by date range AND daily time range
    filtered_data = []
    for order in data:
        try:
            order_datetime = datetime.strptime(order["created_at"], "%Y-%m-%d %H:%M:%S")
            order_date = order_datetime.date()

            # Check if order is within the date range
            if start_date_obj <= order_date <= end_date_obj:
                # Check if order time is within the daily time range
                if is_within_daily_time_range(
                    order_datetime, start_time_obj, end_time_obj
                ):
                    filtered_data.append(order)
        except:
            continue

    # ✅ Normalize filter_by list to lowercase
    filter_by_lower = [f.lower() for f in filter_by]

    # ✅ Filter by clients (only if not ["all"])
    if filter_by_lower and not (
        len(filter_by_lower) == 1 and filter_by_lower[0] == "all"
    ):
        filtered_data = [
            order
            for order in filtered_data
            if order.get("user_name", "").lower() in filter_by_lower
        ]

    # ✅ Filter by status (only if not "all")
    if status.lower() != "all":
        filtered_data = [
            order
            for order in filtered_data
            if order.get("status", "").lower() == status.lower()
        ]

    # Create dummy datetime objects for the reports_client function
    start_dt = datetime.combine(start_date_obj, start_time_obj)
    end_dt = datetime.combine(end_date_obj, end_time_obj)

    print(filtered_data)

    summary = reports_client(filtered_data, start_dt, end_dt)
    return jsonify(summary)


@app.route("/3pl_report", methods=["GET"])
def generate_3pl_report():
    # Read query parameters
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    filter_by = request.args.getlist("filter_by")  # ✅ get multiple values as list
    status = request.args.get("status", "all")

    data = getData(start_date, end_date, "all")

    print("filter_by:", filter_by)

    if filter_by and not ("all" in [f.lower() for f in filter_by]):
        data = [
            order
            for order in data
            if any(
                (
                    (order.get("pickup_task", {}).get("driver_name") or "")
                    .strip()
                    .split(" ")[-1]
                    .upper()
                    == f.upper()
                )
                for f in filter_by
                if (order.get("pickup_task", {}).get("driver_name") or "").strip()
            )
        ]

    # ✅ Filter by status if not ALL
    if status != "all":
        data = [
            order for order in data if str(order.get("status", "")).lower() == status
        ]

    print(data)
    summary = reports_3pl(data)
    return jsonify(summary)


if __name__ == "__main__":
    app.run(debug=False)
