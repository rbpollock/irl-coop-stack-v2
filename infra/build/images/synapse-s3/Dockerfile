# irlcoop/synapse-s3 — stock Synapse + the S3 media storage provider
# (media lands on the shared MinIO instead of the local disk), plus an
# env-render entrypoint so the OIDC/DB/media/TURN secrets flow from the
# container env (derived-key master) instead of being baked into the yaml.
FROM matrixdotorg/synapse:v1.118.0
RUN pip install --no-cache-dir synapse-s3-storage-provider==1.5.0
COPY entrypoint.py /entrypoint.py
RUN chmod +x /entrypoint.py
ENTRYPOINT ["python3", "/entrypoint.py"]
