import os
class LocalStorage:
    mode = "Local SQLite demo mode"

    def list_donations(self):
        with _connect() as conn:
            rows = conn.execute("SELECT * FROM donations ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    def add_donation(self, item):
        with _connect() as conn:
            conn.execute("""
                INSERT INTO donations
                (donation_id, donor_name, food_name, category, quantity, location,
                 expiry_time, notes, image_url, status, claimed_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available', '', ?)
            """, (
                item["donation_id"], item["donor_name"], item["food_name"],
                item["category"], int(item["quantity"]), item["location"],
                item["expiry_time"], item.get("notes", ""), item.get("image_url", ""),
                item["created_at"]
            ))
            conn.commit()

    def update_status(self, donation_id, status, claimed_by=""):
        with _connect() as conn:
            cur = conn.execute(
                "UPDATE donations SET status=?, claimed_by=? WHERE donation_id=?",
                (status, claimed_by, donation_id)
            )
            conn.commit()
            return cur.rowcount > 0

    def upload_image(self, uploaded_file):
        # Local demo mode does not upload files to a cloud bucket.
        return ""

class AWSStorage:
    mode = "AWS DynamoDB + S3"

    def __init__(self, region, table_name, bucket_name):
        import boto3
        session = boto3.Session(region_name=region)
        self.table = session.resource("dynamodb").Table(table_name)
        self.s3 = session.client("s3")
        self.bucket = bucket_name
        self.table_name = table_name
        self.region = region
        # A harmless read validates that the configured table is reachable.
        self.table.load()

    def list_donations(self):
        response = self.table.scan()
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = self.table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        return items

    def add_donation(self, item):
        self.table.put_item(Item=item)

    def update_status(self, donation_id, status, claimed_by=""):
        response = self.table.update_item(
            Key={"donation_id": donation_id},
            UpdateExpression="SET #s = :s, claimed_by = :c",
            ConditionExpression="attribute_exists(donation_id) AND #s = :available",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": status, ":c": claimed_by, ":available": "Available"
            },
            ReturnValues="UPDATED_NEW",
        )
        return bool(response.get("Attributes"))

    def upload_image(self, uploaded_file):
        if not self.bucket:
            return ""
        suffix = Path(uploaded_file.name).suffix.lower()[:10]
        key = f"donation-images/{uuid.uuid4().hex}{suffix}"
        self.s3.upload_fileobj(
            uploaded_file, self.bucket, key,
            ExtraArgs={"ContentType": uploaded_file.type or "application/octet-stream"}
        )
        # Keep an S3 URI; do not make the bucket public.
        return f"s3://{self.bucket}/{key}"

def get_storage():
    mode = os.getenv("FOODBRIDGE_STORAGE", "local").strip().lower()
    if mode != "aws":
        return LocalStorage()

    region = os.getenv("AWS_REGION", "ap-south-1")
    table_name = os.getenv("DYNAMODB_TABLE", "FoodBridgeDonations")
    bucket_name = os.getenv("S3_BUCKET", "")
    try:
        return AWSStorage(region, table_name, bucket_name)
    except Exception as exc:
        raise RuntimeError(
            "AWS mode is enabled but AWS could not be reached. Check AWS credentials, "
            "region, DynamoDB table name, IAM permissions, and S3 bucket. "
            f"Technical detail: {type(exc).__name__}: {exc}"
        ) from exc

