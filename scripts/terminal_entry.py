import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--parse-document":
        from doxa.retrieval.document_worker import main

        main()
    elif len(sys.argv) > 1 and sys.argv[1] == "--resolve-host":
        from doxa.retrieval.dns_worker import main

        main()
    else:
        if len(sys.argv) > 1 and sys.argv[1] == "--cli":
            del sys.argv[1]
        sys._DOXA_TERMINAL_ONLY = True
        from doxa.cli.main import app

        app()
