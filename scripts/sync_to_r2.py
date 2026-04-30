"""
output/intel/ JSON 파일들을 Cloudflare R2에 업로드
파이프라인 완료 후 07:50에 실행
"""
import boto3
import os
from pathlib import Path
from datetime import datetime, timezone

INTEL_DIR = Path("/app/output/intel")
BUCKET = os.environ["R2_BUCKET_NAME"]
ACCOUNT_ID = os.environ["CLOUDFLARE_ACCOUNT_ID"]

FILES_TO_SYNC = {
    "regime.json":        "latest/regime.json",
    "sector_scores.json": "latest/sectors.json",
    "opportunities.json": "latest/screener.json",
    "price_analysis.json":"latest/prices_analysis.json",
}


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def sync_file(client, local_path: Path, r2_key: str) -> bool:
    if not local_path.exists():
        print(f"[SKIP] {local_path} not found")
        return False
    with open(local_path, "rb") as f:
        client.put_object(
            Bucket=BUCKET,
            Key=r2_key,
            Body=f,
            ContentType="application/json",
            CacheControl="public, max-age=3600",
        )
    print(f"[OK] {local_path.name} → r2://{r2_key}")
    return True


def archive_today(client):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for _, r2_key in FILES_TO_SYNC.items():
        archive_key = r2_key.replace("latest/", f"history/{today}/")
        try:
            client.copy_object(
                Bucket=BUCKET,
                CopySource={"Bucket": BUCKET, "Key": r2_key},
                Key=archive_key,
            )
        except Exception:
            pass


def main():
    client = get_r2_client()
    success = sum(
        sync_file(client, INTEL_DIR / local_name, r2_key)
        for local_name, r2_key in FILES_TO_SYNC.items()
    )
    archive_today(client)
    print(f"[DONE] {success}/{len(FILES_TO_SYNC)} files synced")


if __name__ == "__main__":
    main()
