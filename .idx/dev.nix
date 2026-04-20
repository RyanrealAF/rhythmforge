# To learn more about how to use Nix to configure your environment
# see: https://firebase.google.com/docs/studio/customize-workspace
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-24.05"; # or "unstable"

  # Use https://search.nixos.org/packages to find packages
  packages = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.uvicorn
    pkgs.ffmpeg
    pkgs.libsndfile1
    pkgs.git
    pkgs.docker
  ];

  # Sets environment variables in the workspace
  env = {};
  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      # "vscodevim.vim"
    ];

    # Enable previews
    previews = {
      enable = true;
      previews = {
        rhythmforge = {
          command = ["docker" "run" "--rm" "-p" "$PORT:8000" "rhythmforge"};
          manager = "web";
          label = "RhythmForge";
        };
      };
    };

    # Workspace lifecycle hooks
    workspace = {
      # Runs when a workspace is first created
      onCreate = {
        install-deps = "python3.11 -m pip install -r requirements.txt";
      };
      # Runs when the workspace is (re)started
      onStart = {
        build-docker-image = "docker build -t rhythmforge .";
      };
    };
  };
}
