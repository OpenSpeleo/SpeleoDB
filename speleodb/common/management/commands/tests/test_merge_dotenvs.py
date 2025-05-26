import tempfile
from pathlib import Path
from unittest import TestCase

from parameterized.parameterized import parameterized

from speleodb.common.management.commands.merge_prod_dotenvs import Command


class TestMergeDotEnvCommandWithTempfile(TestCase):
    def setUp(self) -> None:
        self.file1 = Path(tempfile.NamedTemporaryFile(mode="w+", delete=False).name)  # noqa: SIM115
        self.file2 = Path(tempfile.NamedTemporaryFile(mode="w+", delete=False).name)  # noqa: SIM115
        self.output_file = Path(
            tempfile.NamedTemporaryFile(mode="w+", delete=False).name  # noqa: SIM115
        )

    def tearDown(self) -> None:
        # Cleanup temporary files
        for file in [self.file1, self.file2, self.output_file]:
            file.unlink()

    @parameterized.expand(
        [
            (["", ""], "\n\n"),
            (["SEP=true", "AR=ator"], "SEP=true\nAR=ator\n"),
            (["A=0", "B=1"], "A=0\nB=1\n"),
            (["X=x\n", "Z=z"], "X=x\n\nZ=z\n"),
            (
                ["DJANGO_SETTINGS=production\n", "POSTGRES_DB=mydb\n"],
                "DJANGO_SETTINGS=production\n\nPOSTGRES_DB=mydb\n\n",
            ),
        ]
    )
    def test_merge_dot_env_files_with_tempfile(
        self, input_contents: list[str], expected_output: str
    ) -> None:
        assert len(input_contents) == 2  # noqa: PLR2004

        # Write test content to input files
        self.file1.write_text(input_contents[0])
        self.file2.write_text(input_contents[1])

        # Call the merge function
        command = Command()
        command.merge_dot_env_files([self.file1, self.file2], self.output_file)

        # Read and verify the merged output
        with self.output_file.open(mode="r") as merged_file:
            actual_content = merged_file.read()
            assert expected_output == actual_content
