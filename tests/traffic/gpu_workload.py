import time
from importlib import import_module


def main() -> None:
    try:
        torch = import_module("torch")
        nn = import_module("torch.nn")
    except ImportError as exc:
        print(exc)
        raise SystemExit("PyTorch is required. Please install torch first.") from exc

    if not torch.cuda.is_available():
        raise SystemExit(
            "No CUDA GPU detected. Please ensure NVIDIA driver/CUDA are ready."
        )

    device = torch.device("cuda")
    torch.backends.cudnn.benchmark = True

    batch_size = 256
    input_dim = 4096
    hidden_dim = 8192
    output_dim = 2048

    model = nn.Sequential(
        nn.Linear(input_dim, hidden_dim),
        nn.GELU(),
        nn.Linear(hidden_dim, hidden_dim),
        nn.GELU(),
        nn.Linear(hidden_dim, output_dim),
    ).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    scaler = torch.amp.GradScaler("cuda", enabled=True)

    step = 0
    start = time.time()

    print(
        f"Start GPU workload on {torch.cuda.get_device_name(0)} | "
        f"batch={batch_size}, in={input_dim}, hidden={hidden_dim}, out={output_dim}"
    )

    try:
        while True:
            x = torch.randn(batch_size, input_dim, device=device)
            y = torch.randn(batch_size, output_dim, device=device)

            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                pred = model(x)
                loss = loss_fn(pred, y)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            step += 1
            if step % 50 == 0:
                torch.cuda.synchronize()
                elapsed = time.time() - start
                ips = step / elapsed
                print(
                    f"step={step} loss={loss.item():.4f} "
                    f"iter/s={ips:.2f} mem={torch.cuda.memory_allocated() / 1024**3:.2f}GB"
                )
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    main()
