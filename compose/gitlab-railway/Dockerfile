FROM gitlab/gitlab-ce:latest

COPY --chmod=755 start /opt/speleodb/start
COPY gitlab.rb bootstrap.rb /opt/speleodb/

ENV GITLAB_OMNIBUS_CONFIG="from_file('/opt/speleodb/gitlab.rb')" \
    GITLAB_POST_RECONFIGURE_SCRIPT="gitlab-rails runner /opt/speleodb/bootstrap.rb" \
    GITLAB_DISABLE_OPENSSH=true

EXPOSE 8080
ENTRYPOINT ["/opt/speleodb/start"]
