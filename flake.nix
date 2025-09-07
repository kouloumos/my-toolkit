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
        pkgs = import nixpkgs { inherit system; };
      in {
        # =====================================================================
        # PACKAGES - Buildable derivations
        # =====================================================================
        packages.default = pkgs.callPackage ./default.nix {};
        
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
          
          # Note: This dev shell includes all runtime dependencies (like ffmpeg for video processing)
          # that are needed by the shell scripts but not automatically available in basic nix shells
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
      nixosModules.default = { config, lib, pkgs, ... }: {
        # Configuration options that users can set
        options = {
          my-toolkit = {
            enable = lib.mkEnableOption "Enable my-toolkit package and services";
            services = {
              media-renamer = lib.mkEnableOption "Enable media-renamer systemd service";
              ebook-organizer = lib.mkEnableOption "Enable ebook-organizer systemd service";
            };
          };
        };

        # Configuration implementation
        config = lib.mkIf config.my-toolkit.enable {
          # Install packages system-wide
          environment.systemPackages = [ 
            self.packages.${pkgs.system}.default
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
                  pkgs.zenity         # GUI dialogs
                ];
                
                serviceConfig = {
                  ExecStart = "${self.packages.${pkgs.system}.default}/bin/media-renamer";
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
                  pkgs.zenity         # GUI dialogs
                  pkgs.inotify-tools  # File system monitoring
                  pkgs.procps         # Process utilities
                  pkgs.dbus           # Inter-process communication
                ];
                
                serviceConfig = {
                  ExecStart = "${self.packages.${pkgs.system}.default}/bin/ebook-organizer";
                  Restart = "always";
                  RestartSec = "5";
                  StandardOutput = "journal";
                  StandardError = "journal";
                };
              };
            })
          ];
        };
      };
    };
}
