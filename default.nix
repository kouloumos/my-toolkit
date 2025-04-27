{ pkgs ? import <nixpkgs> {} }:

let
  # Define dependencies once in a variable we can reference later
  dependencies = with pkgs; [
    ffmpeg
    # Add other dependencies your scripts need
  ];

  # Create Python environment with required packages
  pythonEnv = pkgs.python311.withPackages (ps: with ps; [
    requests # for book-downloader.py
    python-docx # for txt-to-docx.py
  ]);

  # Define script directories
  scriptDirs = [
    ./shell_scripts
    ./systemd_services
  ];

  # Convert scriptDirs to a shell-compatible string
  scriptDirsStr = pkgs.lib.concatStringsSep " " (map (dir: "\"${dir}\"") scriptDirs);

  # Create the my-toolkit command
  mytoolkit = pkgs.writeScriptBin "my-toolkit" ''
    #!${pkgs.bash}/bin/bash

    # Get the directory where my-toolkit is installed
    SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
    PYTHON_SCRIPTS_DIR="$SCRIPT_DIR/../lib/python-scripts"

    # Define script directories
    SCRIPT_DIRS=(${scriptDirsStr})

    function list_scripts() {
      echo "Available scripts:"
      echo
      echo "Shell scripts:"
      for dir in "''${SCRIPT_DIRS[@]}"; do
        for script in "$dir"/*; do
          if [ -x "$script" ] && [ "$(basename "$script")" != "my-toolkit" ]; then
            echo "  $(basename "$script")"
          fi
        done
      done
      echo
      echo "Python scripts:"
      for script in "$PYTHON_SCRIPTS_DIR"/*.py; do
        if [ -f "$script" ]; then
          echo "  $(basename "$script" .py)"
        fi
      done
      echo
      echo "Systemd services:"
      if systemctl --user is-active media-renamer >/dev/null 2>&1; then
        echo "  media-renamer (active)"
      else
        echo "  media-renamer (inactive)"
      fi
      if systemctl --user is-active ebook-organizer >/dev/null 2>&1; then
        echo "  ebook-organizer (active)"
      else
        echo "  ebook-organizer (inactive)"
      fi
    }

    function run_script() {
      local script_name="$1"
      shift

      # Try shell script first
      for dir in "''${SCRIPT_DIRS[@]}"; do
        if [ -x "$dir/$script_name" ]; then
          exec "$dir/$script_name" "$@"
        fi
      done

      # Then try Python script
      if [ -f "$PYTHON_SCRIPTS_DIR/$script_name.py" ]; then
        exec ${pythonEnv}/bin/python3 "$PYTHON_SCRIPTS_DIR/$script_name.py" "$@"
      else
        echo "Error: Script '$script_name' not found"
        exit 1
      fi
    }

    # Main command handling
    if [ $# -eq 0 ]; then
      list_scripts
      exit 1
    fi

    case "$1" in
      list)
        list_scripts
        ;;
      *)
        run_script "$@"
        ;;
    esac
  '';
in
pkgs.stdenv.mkDerivation {
  name = "my-toolkit";
  version = "1.0.0";
  
  # Define runtime dependencies
  buildInputs = dependencies ++ [ pythonEnv ];
  
  # We need makeWrapper to ensure scripts can find dependencies
  nativeBuildInputs = [ pkgs.makeWrapper ];
  
  # No build needed
  dontBuild = true;
  
  # Skip the unpack phase
  dontUnpack = true;
  
  installPhase = ''
    mkdir -p $out/bin
    mkdir -p $out/lib/python-scripts
    
    # Copy all shell scripts and make them executable
    for dir in ${scriptDirsStr}; do
      for file in $(find $dir -type f -name "*.sh"); do
        script_name=$(basename $file .sh)
        cp $file $out/bin/$script_name
        chmod +x $out/bin/$script_name
        
        # Wrap the script with necessary runtime dependencies
        wrapProgram $out/bin/$script_name --prefix PATH : ${pkgs.lib.makeBinPath dependencies}
      done
    done

    # Copy Python scripts
    cp ${./python_scripts}/*.py $out/lib/python-scripts/

    # Install my-toolkit command
    cp ${mytoolkit}/bin/my-toolkit $out/bin/
    chmod +x $out/bin/my-toolkit
  '';
  
  meta = with pkgs.lib; {
    description = "An opinionated collection of utility scripts";
    license = licenses.mit;
    platforms = platforms.linux;
    maintainers = [ "kouloumos" ];
  };
}