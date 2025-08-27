import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)
CORS(app)

VERDI_API_KEY = os.environ.get("VERDI_API_KEY")


def getData(start_date, end_date, filter_by):
    print("filter_by in getData:", filter_by)
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

    from datetime import datetime


from collections import defaultdict


def table_data_rows(data):
    drivers = defaultdict(lambda: {"Amount": 0, "Orders": 0, "Times": []})

    for order in data:
        driver = order.get("pickup_task", {}).get("driver_name", "")
        amount_str = order.get("amount")
        created_str = order.get("created_at")
        successful_str = order.get("delivery_task", {}).get("successful_at")

        # Parse amount
        try:
            amount = round(abs(float(amount_str)), 2)
        except:
            amount = 0

        # Parse time taken
        time_taken = None
        if created_str and successful_str:
            try:
                created = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
                successful = datetime.strptime(successful_str, "%Y-%m-%d %H:%M:%S")
                time_taken = round((successful - created).total_seconds() / 60, 2)
            except:
                pass

        # Update driver's stats
        drivers[driver]["Amount"] += amount
        drivers[driver]["Orders"] += 1
        if time_taken is not None:
            drivers[driver]["Times"].append(time_taken)

    # Build final rows
    rows = []
    for driver, stats in drivers.items():
        avg_time = (
            round(sum(stats["Times"]) / len(stats["Times"]), 2)
            if stats["Times"]
            else None
        )
        rows.append(
            {
                "Driver": driver,
                "Amount": round(stats["Amount"], 2),
                "Orders": stats["Orders"],
                "Average Time Taken (min)": avg_time,
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


@app.route("/3pl_report", methods=["GET"])
def generate_3pl_report():
    # Read query parameters
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    filter_by = request.args.getlist("filter_by")  # ✅ get multiple values as list
    print(f"Generating report from {start_date} to {end_date} for filters: {filter_by}")

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

    summary = reports_3pl(data)
    return jsonify(summary)


if __name__ == "__main__":
    app.run(debug=False)
