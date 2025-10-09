# **ZODEL: An Experimental LLM Orchestration Framework**

**Designed by ZAVIER LI**

## **1\. Introduction**

**ZODEL** is an experimental, Gradio-based framework for orchestrating Large Language Models (LLMs). It provides a unified interface for interacting with various LLM APIs, including local models via **Ollama** and cloud-based, **OpenAI-compatible** services like **GenStudio**.

The primary goal of ZODEL is to serve as a testbed for innovative features in LLM interaction and workflow management. The two flagship features of this framework are:

* **Dynamic Model Routing**: A Classifier-Labels method that automatically routes user queries to the most suitable model based on the nature of the task.  
* **Zflow Language**: A concise, powerful, and intuitive domain-specific language (DSL) for designing and executing complex, multi-step LLM workflows.


## **2\. Core Features**

* **Universal API Connectivity**: Seamlessly connects to different LLM backends through a unified prefix-based system (Ollama:, Cloud:, GenStudio:).  
* **Dynamic Model Routing**: Automatically selects the best model for a given prompt using a customizable classification system. Users can define any number of Labels (e.g., logical, creative-writing) and map them to specific Output Models.  
* **Zflow Orchestration Language**: A built-in language and interpreter that allows users to design, script, and execute complex LLM workflows directly within the chat interface.  
* **Streaming First**: All interactions, including complex Zflow workflows, support full streaming for a real-time, responsive user experience.  
* **User-Friendly Interface**: A clean and modern UI built with Gradio, featuring chat management, a dark mode toggle, and a detailed settings panel.

## **3\. Installation and Setup**

### **Prerequisites**

* Python 3.8 or higher  
* (Optional) [Ollama](https://ollama.com/) installed and running for local model support.

### **1\. Clone the Repository**

git clone \[https://github.com/Felikspa/Zodel.git\]
cd zodel

### **2\. Install Dependencies**

pip install \-r requirements.txt

### **3\. Configure Environment Variables**

Create a .env file in the root directory of the project by copying the example file:

cp .env.example .env

Now, edit the .env file with your API keys and base URLs:

\# For local Ollama models  
OLLAMA\_BASE\_URL="http://localhost:11434"

\# For standard OpenAI-compatible services  
OPENAI\_API\_KEY="sk-..."  
OPENAI\_BASE\_URL="\[https://api.openai.com/v1\](https://api.openai.com/v1)"

\# For GenStudio services  
GENSTUDIO\_API\_KEY="your-genstudio-api-key"  
GENSTUDIO\_BASE\_URL="your-genstudio-base-url"

The framework will automatically detect and initialize clients for which the necessary environment variables are provided.

## **4\. Quick Start**

Run the main application file from the project's root directory:

python main.py

The application will launch a local Gradio server. Open the provided URL (e.g., http://127.0.0.1:7860) in your browser to start using ZODEL.

## **5\. Features in Detail**

### **5.1. Dynamic Model Routing (Auto-selected Mode)**

This mode automates the selection of the most appropriate LLM for a given task. It follows a Classifier \-\> Label \-\> Model pipeline.

#### **How It Works**

1. **Input**: The user sends a prompt.  
2. **Classification**: A **Classifier Model (CM)** analyzes the prompt based on a specific system prompt.  
3. **Labeling**: The CM outputs a single-word **Label** (e.g., logical, nonlogical) that categorizes the user's intent.  
4. **Routing**: The framework maps this label to a pre-configured **Output Model (OM)**.  
5. **Execution**: The original user prompt is sent to the selected OM for the final, streamed response.

A typical system prompt for the Classifier Model looks like this:

"You are a routing agent. Classify the user's prompt as 'logical' if it requires complex reasoning, calculation, or fact retrieval. Otherwise, classify it as 'nonlogical' for general conversation, creative writing, or simple greetings. Respond ONLY with the single word: logical or nonlogical."

This system is highly extensible. Users can define any number of custom Label \-\> Output Model rules in the settings panel, allowing for fine-grained control over task routing. If the classification fails for any reason, the system gracefully falls back to the model defined in the first rule.

### **5.2. Zflow: Workflow Orchestration Language**

When you select "Zflow" from the main model dropdown, the input box transforms into a real-time interpreter for the Zflow language. Zflow allows you to programmatically design and execute LLM workflows with a simple, intuitive syntax.

#### **Basic Syntax**

Zflow has three fundamental variable types, distinguished by their names:

* **Model (A, B, ...)**: A single uppercase letter representing a full model name.  
* **Prompt (p1, p\_task, ...)**: Starts with p, representing a system prompt.  
* **Input (i, i1, ...)**: Starts with i, representing user content or intermediate data.

**Assignment:** Variables are assigned using \=, with statements separated by commas, spaces, or newlines.

A \= GenStudio:qwen2.5-72b-instruct  
i1 \= "What is the philosophical significance of Wittgenstein's shift in thought?"  
p1 \= "Analyze the internal, philosophical reasons for this shift."

#### **Workflow Structure**

The core of Zflow is the workflow statement, which defines the flow of data between operators.

* \-\> (Sequential Operator): The output of the left-hand side becomes the input for the right-hand side.  
* {} (Parallel Operator): The input is sent to all operators within the braces simultaneously. Their outputs are then concatenated and passed to the next stage.  
* C\_p2(i2) (Extra Input): An optional syntax to provide an additional input to an operator alongside the data from the main pipeline.

**Example Workflow:**

The following script first asks Model A and Model B to analyze a question from two different perspectives in parallel. Then, it sends the original question (i) along with both of their answers to Model C for a final, synthesized response.


\# 1\. Variable Assignments  
A \= GenStudio:qwen2.5-72b-instruct  
B \= GenStudio:deepseek-v3  
C \= GenStudio:deepseek-v3.2-exp

i \= 'Why did Wittgenstein undergo a major shift in his later philosophy, so different from his early ideas?'

p1 \= '... explain the internal reasons for this situation ...'  
p2 \= '... explain the external reasons for this situation ...'  
p3 \= '... combine their views into a complete answer.'

\# 2\. Workflow Definition  
i \-\> {A\_p1, B\_p2} \-\> C\_p3(i)

## **6\. Vision and Future Work**

ZODEL is an evolving project with a clear vision for the future of LLM orchestration.

1. **Enhanced Classifier**: Evolve the Classifier-Labels method to allow each Output Model to have its own unique prompt, transforming it into a Classifier \-\> Operator system for more specialized task handling.  
2. **Advanced Zflow Syntax**:  
   * Introduce workflow assignment (e.g., my\_flow \= i \-\> A\_p1) to create reusable and composable workflows.  
   * Define binary operations using LLMs as logic units (e.g., result \= compare(A\_p1(i), B\_p2(i))).  
3. **Multimodality**: Extend the Zflow concept beyond text to orchestrate multimodal models, enabling programmatic processing of images, audio, and video within the same framework.

## **7\. Author**

This project was designed and developed by **ZAVIER LI**.

## **8\. License**

This project is licensed under the MIT License. See the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.
