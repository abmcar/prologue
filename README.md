# Prologue

Artifact for the paper *Prologue: Issuing Ethereum Storage Reads When Their Keys Bind*.

Prologue is a block-execution runtime built in the reth Ethereum client. At compile time, an analysis of each contract's bytecode extracts an access plan, a function from a call's inputs to the storage keys the call may read. At run time, Prologue evaluates the callee's plan when a call starts and issues the call's reads together, in parallel.

This repository will hold the Prologue patch for reth 2.9.0, the plan analyzer and evaluator, the scripts that build the plan library, the evaluation and plotting scripts, and instructions to reproduce the results.
