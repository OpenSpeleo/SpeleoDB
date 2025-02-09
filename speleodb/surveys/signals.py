from django.dispatch import Signal
from django.dispatch import receiver

git_push_done = Signal()


@receiver(git_push_done)
def notify_admin(sender, **kwargs):
    print(f"Git Push Executed! {sender=} | Task details: {kwargs=}")
