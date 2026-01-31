{
  # Basic flake metadata
  description = "An opinionated collection of utility scripts";

  # =============================================================================
  # INPUTS - External dependencies
  # =============================================================================
  inputs = {
    # Main Nix package repository (unstable for latest packages)
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    
    # System architecture definitions (supports aarch64-linux, x86_64-linux, etc.)
    systems.url = "github:nix-systems/default-linux";
    
    # Utility functions for multi-system flake support
    flake-utils = {
      url = "github:numtide/flake-utils";
      inputs.systems.follows = "systems";
    };
  };

  # =============================================================================
  # OUTPUTS - What this flake provides
  # =============================================================================
  outputs = { self, nixpkgs, flake-utils, ... }: 
    # Generate system-specific outputs
    (flake-utils.lib.eachDefaultSystem (system:
      let
        # Import nixpkgs for the current system
        # Allow insecure packages (squid) - TODO: replace with secure alternative
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowInsecure = true;
            permittedInsecurePackages = [
              "squid-7.0.1"
            ];
          };
        };
      in {
        # =====================================================================
        # PACKAGES - Buildable derivations
        # =====================================================================
        packages.default = pkgs.callPackage ./default.nix {};

        # =====================================================================
        # CHECKS - Tests that run with `nix flake check`
        # =====================================================================
        checks = {
          # Run unit tests
          unit-tests = pkgs.stdenv.mkDerivation {
            name = "my-toolkit-tests";
            src = ./.;

            nativeBuildInputs = [
              (pkgs.python311.withPackages (ps: with ps; [
                requests
                python-docx
                subliminal
              ]))
            ];

            buildPhase = ''
              # Run unit tests
              python3 -m unittest discover -s tests -p "test_*.py" -v
            '';

            installPhase = ''
              mkdir -p $out
              echo "Tests passed" > $out/test-results.txt
            '';

            doCheck = true;
          };

          # Check that all Python scripts have valid syntax
          python-syntax = pkgs.runCommand "check-python-syntax" {
            nativeBuildInputs = [ pkgs.python311 ];
          } ''
            echo "Checking Python syntax..."
            for script in ${./python_scripts}/*.py; do
              echo "Checking $script"
              ${pkgs.python311}/bin/python3 -m py_compile "$script"
            done
            mkdir -p $out
            echo "All Python scripts have valid syntax" > $out/result.txt
          '';

          # Check that all shell scripts have valid syntax
          shell-syntax = pkgs.runCommand "check-shell-syntax" {
            nativeBuildInputs = [ pkgs.shellcheck pkgs.bash ];
          } ''
            echo "Checking shell script syntax..."
            for script in ${./shell_scripts}/*.sh; do
              echo "Checking $script"
              ${pkgs.bash}/bin/bash -n "$script"
            done
            mkdir -p $out
            echo "All shell scripts have valid syntax" > $out/result.txt
          '';

          # Format check - ensure CLAUDE.md exists and is not empty
          documentation = pkgs.runCommand "check-documentation" {} ''
            if [ ! -f ${./CLAUDE.md} ]; then
              echo "Error: CLAUDE.md not found"
              exit 1
            fi
            if [ ! -s ${./CLAUDE.md} ]; then
              echo "Error: CLAUDE.md is empty"
              exit 1
            fi
            mkdir -p $out
            echo "Documentation check passed" > $out/result.txt
          '';
        };
        
        # =====================================================================
        # OVERLAYS - Package overrides for other flakes/projects
        # =====================================================================

        # =====================================================================
        # DEVELOPMENT SHELLS - Environment for development
        # =====================================================================
        devShells.default = pkgs.mkShell {
          # Include our package and all its dependencies
          packages = [ self.packages.${system}.default ];
          inputsFrom = [ self.packages.${system}.default ];

          shellHook = ''
            export MY_TOOLKIT_DEV_MODE=1
            # Try using system certs first, fallback to Nix certs
            export SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
            export NIX_SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt"
            export REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt"
            export CURL_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt"
            export SSL_CERT_DIR="/etc/ssl/certs"
            echo "🛠️  My-Toolkit Development Environment"
            echo "📦 Run scripts directly: my-toolkit <script-name> [args]"
            echo "📝 Available scripts: my-toolkit list"
            echo "⚡ Changes to scripts are immediately available!"
            echo ""
            echo "⚠️  Note: Squid is marked as insecure (will be replaced in future)"
            echo ""
          '';

          # Note: This dev shell includes all runtime dependencies (like ffmpeg for video processing)
          # that are needed by the shell scripts but not automatically available in basic nix shells
        };

        # =====================================================================
        # APPS - Standalone applications that can be run with `nix run`
        # =====================================================================
        # These apps allow users to run commands without installation:
        #   nix run github:kouloumos/my-toolkit#torrent-search -- "Movie Name"
        #   nix run github:kouloumos/my-toolkit#torrent-watch -- 1
        apps = let
          mkApp = scriptName: {
            type = "app";
            program = "${pkgs.writeShellScript "run-${scriptName}" ''
              exec ${self.packages.${system}.default}/bin/my-toolkit ${scriptName} "$@"
            ''}";
          };
        in {
          # Torrent management commands
          torrent-search = mkApp "torrent-search";
          torrent-list = mkApp "torrent-list";
          torrent-watch = mkApp "torrent-watch";
          torrent-cleanup = mkApp "torrent-cleanup";

          # Utility commands
          download-torrent = mkApp "download-torrent";
          find-subtitles = mkApp "find-subtitles";
          video2gif = mkApp "video2gif";
          upload-to-remarkable = mkApp "upload-to-remarkable";
          book-downloader = mkApp "book-downloader";

          # Development workflow
          worktree = mkApp "worktree";

          # Proxy and diagnostics
          proxy-setup = mkApp "proxy-setup";
          health-check = mkApp "health-check";

          # Main my-toolkit command as default app
          default = {
            type = "app";
            program = "${self.packages.${system}.default}/bin/my-toolkit";
          };
        };
      }
    )) // {
      # =====================================================================
      # OVERLAYS - Package overrides for other flakes/projects
      # =====================================================================
      overlays.default = final: prev: {
        my-toolkit = self.packages.${prev.system}.default;
      };

      # =====================================================================
      # NIXOS MODULE - System integration for NixOS (system-independent)
      # =====================================================================
      nixosModules.default = { config, lib, pkgs, ... }:
        let
          # Use the system architecture to get the right package
          system = pkgs.system;
          mytoolkitPackage = self.packages.${system}.default;
        in {
        # Configuration options that users can set
        options = {
          my-toolkit = {
            enable = lib.mkEnableOption "Enable my-toolkit package and services";
            services = {
              media-renamer = lib.mkEnableOption "Enable media-renamer systemd service";
              ebook-organizer = lib.mkEnableOption "Enable ebook-organizer systemd service";
              residential-proxy = lib.mkEnableOption "Enable residential proxy (Squid) systemd service";
            };
          };
        };

        # Configuration implementation
        config = lib.mkIf config.my-toolkit.enable {
          # Install packages system-wide using my-toolkit's pre-built package
          environment.systemPackages = [
            mytoolkitPackage
            pkgs.python311  # Required for Python scripts
          ];

          # =============================================================
          # SYSTEMD USER SERVICES - Automated background tasks
          # =============================================================
          systemd.user.services = lib.mkMerge [
              # Media Renamer Service
              (lib.mkIf config.my-toolkit.services.media-renamer {
                media-renamer = {
                  description = "Automatically rename screenshots and screencasts";
                  wantedBy = [ "default.target" ];

                  # Required system packages for the service
                  path = [
                    pkgs.inotify-tools  # File system monitoring
                    (if (builtins.hasAttr "zenity" pkgs) then pkgs.zenity else pkgs.gnome.zenity)  # GUI dialogs
                  ];

                  serviceConfig = {
                    ExecStart = "${mytoolkitPackage}/bin/media-renamer";
                    Restart = "always";
                    RestartSec = "5";
                    StandardOutput = "journal";
                    StandardError = "journal";
                  };
                };
              })

              # E-book Organizer Service
              (lib.mkIf config.my-toolkit.services.ebook-organizer {
                ebook-organizer = {
                  description = "Automatically organize downloaded e-books";
                  wantedBy = [ "default.target" ];

                  # Required system packages for the service
                  path = [
                    pkgs.calibre        # E-book management
                    (if (builtins.hasAttr "zenity" pkgs) then pkgs.zenity else pkgs.gnome.zenity)  # GUI dialogs
                    pkgs.inotify-tools  # File system monitoring
                    pkgs.procps         # Process utilities
                    pkgs.dbus           # Inter-process communication
                  ];

                  serviceConfig = {
                    ExecStart = "${mytoolkitPackage}/bin/ebook-organizer";
                    Restart = "always";
                    RestartSec = "5";
                    StandardOutput = "journal";
                    StandardError = "journal";
                  };
                };
              })

              # Residential Proxy Service
              (lib.mkIf config.my-toolkit.services.residential-proxy {
                residential-proxy = {
                  description = "Residential Proxy (Squid) for My Toolkit";
                  after = [ "network.target" ];
                  wantedBy = [ "default.target" ];

                  # Path to Squid binary from system's pkgs
                  path = [ pkgs.squid ];

                  serviceConfig = {
                    Type = "forking";
                    PIDFile = "%t/squid.pid";
                    ExecStart = "${pkgs.squid}/bin/squid -f %h/.config/my-toolkit/squid.conf";
                    ExecReload = "${pkgs.squid}/bin/squid -k reconfigure";
                    ExecStop = "${pkgs.squid}/bin/squid -k shutdown";
                    KillMode = "mixed";
                    Restart = "on-failure";
                    RestartSec = "5";

                    # Security settings
                    PrivateTmp = true;
                    NoNewPrivileges = true;
                  };

                  preStart = ''
                    # Check if configuration exists
                    if [ ! -f "$HOME/.config/my-toolkit/squid.conf" ]; then
                      echo "Error: Squid configuration not found at $HOME/.config/my-toolkit/squid.conf"
                      echo "Run: my-toolkit proxy-setup configure <proxy-url>"
                      exit 1
                    fi

                    # Create cache directory in user space
                    mkdir -p $HOME/.cache/my-toolkit/squid

                    # Initialize Squid cache if needed
                    if [ ! -d "$HOME/.cache/my-toolkit/squid/00" ]; then
                      ${pkgs.squid}/bin/squid -z -f $HOME/.config/my-toolkit/squid.conf
                    fi
                  '';
                };
              })
            ];
          };
        };
    };
}
