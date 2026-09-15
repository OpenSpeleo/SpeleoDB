FROM gitlab/gitlab-ce:19.3.2-ce.0@sha256:05453dd1d9aba27c2c487613141596868409b4d03247647f7d66cb0b36f321b8

COPY --chmod=755 start /opt/speleodb/start
COPY gitlab.rb bootstrap.rb /opt/speleodb/

ENV GITLAB_OMNIBUS_CONFIG="from_file('/opt/speleodb/gitlab.rb')" \
    GITLAB_POST_RECONFIGURE_SCRIPT="gitlab-rails runner /opt/speleodb/bootstrap.rb" \
    GITLAB_DISABLE_OPENSSH=true

EXPOSE 8080
ENTRYPOINT ["/opt/speleodb/start"]
