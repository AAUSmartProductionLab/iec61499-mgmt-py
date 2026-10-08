# 4diac FORTE for a Raspberry Pi (aarch64): the static binary from build-modules.ps1 -Config pi/modules-pi.
# Alpine only for a shell when debugging; FORTE itself needs no libraries.
FROM alpine:3.20
COPY forte /usr/local/bin/forte
# The boot file (forte.fboot) is read from the working directory, a volume (see compose.yaml).
WORKDIR /forte
EXPOSE 61499 4840
ENTRYPOINT ["/usr/local/bin/forte", "-c", "0.0.0.0:61499"]
