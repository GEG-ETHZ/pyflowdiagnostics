Installation
============

You can install pyflowdiagnostics either via ``conda``:

.. code-block:: console

   conda install -c conda-forge pyflowdiagnostics

or via ``pip``:

.. code-block:: console

   pip install pyflowdiagnostics

Requirements are the modules ``numpy``, ``scipy``, ``pandas``, ``xlswriter``,
``h5py``, and ``pymatsolver``.

Alternatively, you can clone or download the repo and run within the top directory

.. code-block:: console

   python -m pip install .


Dependencies
------------

Required core dependencies are installed via ``environment.yml``. Additionally,
we utilize `sr3_reader
<https://github.com/nikolai-andrianov/sr3_reader/blob/main/README.md>`_
(slightly modified to support LGR) for processing CMG binary outputs.
