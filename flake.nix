{
  description = "SpeleoDB tools and libraries; uv and npm manage application dependencies";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "aarch64-linux" "x86_64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      environments = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          # 26.05's uv is too old for this project's dependency overrides.
          uvVersion = "0.12.17";
          uvSource = pkgs.fetchzip {
            url = "https://github.com/astral-sh/uv/releases/download/${uvVersion}/uv-${pkgs.stdenv.hostPlatform.parsed.cpu.name}-unknown-linux-musl.tar.gz";
            hash = {
              aarch64-linux = "sha256-2bxVbk+Kvdw8s1ekTcZecb/gz2+nAHfzwZ3ExuMkWj0=";
              x86_64-linux = "sha256-gjkBWiVLCz3xC8FLudveO0qVGI+hPrvZ3A7FJnxB85o=";
            }.${system};
          };
          uvTool = pkgs.runCommand "uv-${uvVersion}" {} ''
            mkdir -p "$out/bin"
            ln -s ${uvSource}/uv ${uvSource}/uvx "$out/bin/"
          '';
          nodeMajor = pkgs.lib.removeSuffix "\n" (builtins.readFile ./.node-version);
          libs = with pkgs; [ stdenv.cc.cc.lib zlib openssl libffi libpq ];
          runtime = with pkgs; [
            python314 bashInteractive coreutils gitMinimal ffmpeg-headless nix
            curl gnugrep gnused findutils gnutar gzip xz
          ] ++ libs;
          development = with pkgs; [
            uvTool pkgs."nodejs_${nodeMajor}" stdenv.cc gnumake pkg-config libpq.pg_config
            gettext watchman wget vim openssh bash-completion procps shadow sudo pam nix-ld
            glibc.bin glibc.out glibc.getent
          ];
          environment = name: paths: pkgs.buildEnv {
            inherit name paths;
            pathsToLink = [ "/bin" "/lib" "/libexec" "/share" ];
          };
        in {
          packages = {
            runtime = environment "speleodb-runtime" runtime;
            development = environment "speleodb-development" development;
            monorepo = environment "speleodb-monorepo" (development ++ [ pkgs.rustc pkgs.cargo ]);
          };
          shell = pkgs.mkShell {
            packages = runtime ++ development;
            env.NIX_LD = pkgs.stdenv.cc.bintools.dynamicLinker;
            env.NIX_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath (libs ++ [ pkgs.glibc ]);
          };
        });
    in {
      packages = forAllSystems (system: environments.${system}.packages);
      devShells = forAllSystems (system: { default = environments.${system}.shell; });
    };
}
